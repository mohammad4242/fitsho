import AVFoundation
import CoreImage
import Foundation
import ImageIO
import MediaPipeTasksVision
import NitroModules
import UIKit
import VisionCamera

public final class FiticianBodyVision: HybridFiticianBodyVisionSpec {
  public let contractVersion = "1.0"

  private static let MODEL_STATUS_READY = "ready"
  private static let MODEL_STATUS_NOT_PACKAGED = "not-packaged"
  private static let poseModelName = "pose_landmarker_lite"
  private static let segmentationModelName = "selfie_segmenter"
  private static let modelDirectory = "body_vision"
  private static let minPoseConfidence: Float = 0.5

  private let processingLock = NSLock()
  private let metricsLock = NSLock()
  private let imageContext = CIContext()

  private var poseLandmarker: PoseLandmarker?
  private var imageSegmenter: ImageSegmenter?
  private var nativeModelStatus = FiticianBodyVision.MODEL_STATUS_NOT_PACKAGED
  private var processedFrameCount = 0
  private var droppedFrameCount = 0
  private var totalFrameDurationNanoseconds: UInt64 = 0
  private var maxFrameDurationNanoseconds: UInt64 = 0

  public override init() {
    super.init()
    configureModels()
  }

  public var modelStatus: String {
    metricsLock.lock()
    defer { metricsLock.unlock() }
    return nativeModelStatus
  }

  public func process(frame: any HybridFrameSpec) throws -> NativeBodyVisionResult {
    processingLock.lock()
    defer { processingLock.unlock() }

    guard let poseLandmarker, let imageSegmenter, modelStatus == Self.MODEL_STATUS_READY else {
      throw BodyVisionError.modelsNotPackaged
    }

    let startedAt = DispatchTime.now().uptimeNanoseconds
    let image = try makeMediaPipeImage(from: frame)
    let poseResult = try poseLandmarker.detect(image: image)
    let segmentationResult = try imageSegmenter.segment(image: image)
    guard let segmentationMask = segmentationResult.confidenceMasks?.first else {
      throw BodyVisionError.segmentationMaskMissing
    }

    let result = NativeBodyVisionResult(
      landmarks: poseResult.landmarks.map { pose in
        pose.map { landmark in
          NativeBodyLandmark(
            x: Double(landmark.x),
            y: Double(landmark.y),
            z: Double(landmark.z),
            visibility: Double(landmark.visibility?.doubleValue ?? 0),
          )
        }
      },
      mask: NativeBodyVisionMask(
        width: Double(segmentationMask.width),
        height: Double(segmentationMask.height),
        values: try makeArrayBuffer(from: segmentationMask),
      ),
      frame: NativeBodyVisionFrame(
        width: frame.width,
        height: frame.height,
        timestamp: frame.timestamp,
      ),
    )

    recordProcessedFrame(durationNanoseconds: DispatchTime.now().uptimeNanoseconds - startedAt)
    return result
  }

  public func recordDroppedFrame() throws {
    metricsLock.lock()
    droppedFrameCount += 1
    metricsLock.unlock()
  }

  public func benchmark() throws -> NativeBodyVisionBenchmark {
    metricsLock.lock()
    let processed = processedFrameCount
    let dropped = droppedFrameCount
    let totalDuration = totalFrameDurationNanoseconds
    let maxDuration = maxFrameDurationNanoseconds
    let status = nativeModelStatus
    metricsLock.unlock()

    return NativeBodyVisionBenchmark(
      frameCount: Double(processed + dropped),
      processedFrameCount: Double(processed),
      droppedFrameCount: Double(dropped),
      averageFrameDurationMs: processed == 0
        ? 0
        : Double(totalDuration) / Double(processed) / 1_000_000,
      maxFrameDurationMs: Double(maxDuration) / 1_000_000,
      modelStatus: status,
    )
  }

  public func dispose() {
    processingLock.lock()
    poseLandmarker = nil
    imageSegmenter = nil
    processingLock.unlock()

    metricsLock.lock()
    nativeModelStatus = Self.MODEL_STATUS_NOT_PACKAGED
    metricsLock.unlock()
  }

  private func configureModels() {
    guard let poseModelPath = Self.modelPath(
      named: Self.poseModelName,
      extension: "task"
    ), let segmentationModelPath = Self.modelPath(
      named: Self.segmentationModelName,
      extension: "tflite"
    ) else {
      return
    }

    let poseOptions = PoseLandmarkerOptions()
    poseOptions.runningMode = .image
    poseOptions.numPoses = 1
    poseOptions.minPoseDetectionConfidence = Self.minPoseConfidence
    poseOptions.minPosePresenceConfidence = Self.minPoseConfidence
    poseOptions.minTrackingConfidence = Self.minPoseConfidence
    poseOptions.shouldOutputSegmentationMasks = false
    poseOptions.baseOptions.modelAssetPath = poseModelPath
    poseOptions.baseOptions.delegate = .CPU

    let segmentationOptions = ImageSegmenterOptions()
    segmentationOptions.runningMode = .image
    segmentationOptions.shouldOutputCategoryMask = false
    segmentationOptions.shouldOutputConfidenceMasks = true
    segmentationOptions.baseOptions.modelAssetPath = segmentationModelPath
    segmentationOptions.baseOptions.delegate = .CPU

    do {
      poseLandmarker = try PoseLandmarker(options: poseOptions)
      imageSegmenter = try ImageSegmenter(options: segmentationOptions)
      nativeModelStatus = Self.MODEL_STATUS_READY
    } catch {
      poseLandmarker = nil
      imageSegmenter = nil
      nativeModelStatus = Self.MODEL_STATUS_NOT_PACKAGED
    }
  }

  private func makeMediaPipeImage(from frame: any HybridFrameSpec) throws -> MPImage {
    guard frame.isValid else {
      throw BodyVisionError.invalidFrame
    }
    guard let nativeFrame = frame as? NativeFrame,
          let sourcePixelBuffer = nativeFrame.sampleBuffer?.imageBuffer else {
      throw BodyVisionError.nativePixelBufferMissing
    }

    let pixelBuffer = try makeBgraPixelBuffer(from: sourcePixelBuffer)
    guard frame.isMirrored else {
      return try MPImage(
        pixelBuffer: pixelBuffer,
        orientation: uiImageOrientation(from: frame.orientation),
      )
    }

    // MediaPipe Tasks rejects mirrored orientations. Materialize the camera
    // transform before inference so front-camera frames keep Android parity.
    let normalizedPixelBuffer = try makeBgraPixelBuffer(
      from: pixelBuffer,
      applying orientation: cgImageOrientation(from: frame.orientation, mirrored: true),
    )
    return try MPImage(pixelBuffer: normalizedPixelBuffer, orientation: .up)
  }

  private func makeBgraPixelBuffer(from source: CVPixelBuffer) throws -> CVPixelBuffer {
    if CVPixelBufferGetPixelFormatType(source) == kCVPixelFormatType_32BGRA {
      return source
    }

    let width = CVPixelBufferGetWidth(source)
    let height = CVPixelBufferGetHeight(source)
    var destination: CVPixelBuffer?
    let attributes: CFDictionary = [
      kCVPixelBufferCGImageCompatibilityKey as String: true,
      kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
    ] as CFDictionary
    let status = CVPixelBufferCreate(
      kCFAllocatorDefault,
      width,
      height,
      kCVPixelFormatType_32BGRA,
      attributes,
      &destination,
    )
    guard status == kCVReturnSuccess, let destination else {
      throw BodyVisionError.pixelBufferConversionFailed
    }

    imageContext.render(CIImage(cvPixelBuffer: source), to: destination)
    return destination
  }

  private func makeBgraPixelBuffer(
    from source: CVPixelBuffer,
    applying orientation: CGImagePropertyOrientation,
  ) throws -> CVPixelBuffer {
    let orientedImage = CIImage(cvPixelBuffer: source).oriented(orientation)
    let extent = orientedImage.extent.integral
    let width = Int(extent.width)
    let height = Int(extent.height)
    guard width > 0, height > 0 else {
      throw BodyVisionError.pixelBufferConversionFailed
    }

    var destination: CVPixelBuffer?
    let attributes: CFDictionary = [
      kCVPixelBufferCGImageCompatibilityKey as String: true,
      kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
    ] as CFDictionary
    let status = CVPixelBufferCreate(
      kCFAllocatorDefault,
      width,
      height,
      kCVPixelFormatType_32BGRA,
      attributes,
      &destination,
    )
    guard status == kCVReturnSuccess, let destination else {
      throw BodyVisionError.pixelBufferConversionFailed
    }

    let translatedImage = orientedImage.transformed(
      by: CGAffineTransform(translationX: -extent.minX, y: -extent.minY),
    )
    imageContext.render(
      translatedImage,
      to: destination,
      bounds: CGRect(origin: .zero, size: extent.size),
      colorSpace: CGColorSpaceCreateDeviceRGB(),
    )
    return destination
  }

  private func makeArrayBuffer(from mask: Mask) throws -> ArrayBuffer {
    let width = Int(mask.width)
    let height = Int(mask.height)
    guard width > 0, height > 0 else {
      throw BodyVisionError.segmentationMaskMissing
    }

    let byteCount = width * height * MemoryLayout<Float>.size
    let data = Data(bytes: mask.float32Data, count: byteCount)
    return try ArrayBuffer.copy(data: data)
  }

  private func recordProcessedFrame(durationNanoseconds: UInt64) {
    metricsLock.lock()
    processedFrameCount += 1
    totalFrameDurationNanoseconds += durationNanoseconds
    maxFrameDurationNanoseconds = max(maxFrameDurationNanoseconds, durationNanoseconds)
    metricsLock.unlock()
  }

  private static func modelPath(named name: String, extension fileExtension: String) -> String? {
    for bundle in resourceBundles() {
      let candidates = [
        bundle.url(forResource: name, withExtension: fileExtension),
        bundle.url(
          forResource: name,
          withExtension: fileExtension,
          subdirectory: modelDirectory,
        ),
      ]
      for candidate in candidates {
        guard let candidate, FileManager.default.fileExists(atPath: candidate.path) else {
          continue
        }
        return candidate.path
      }
    }
    return nil
  }

  private static func resourceBundles() -> [Bundle] {
    var bundles = [Bundle(for: FiticianBodyVision.self), Bundle.main]
    let anchors = bundles
    for anchor in anchors {
      guard let bundleURL = anchor.url(
        forResource: "FiticianBodyVisionResources",
        withExtension: "bundle",
      ), let resourceBundle = Bundle(url: bundleURL) else {
        continue
      }
      bundles.append(resourceBundle)
    }
    return bundles
  }

  private func uiImageOrientation(
    from orientation: CameraOrientation,
  ) -> UIImage.Orientation {
    switch orientation {
    case .up:
      return .up
    case .right:
      return .right
    case .down:
      return .down
    case .left:
      return .left
    }
  }

  private func cgImageOrientation(
    from orientation: CameraOrientation,
    mirrored: Bool,
  ) -> CGImagePropertyOrientation {
    switch orientation {
    case .up:
      return mirrored ? .upMirrored : .up
    case .right:
      return mirrored ? .rightMirrored : .right
    case .down:
      return mirrored ? .downMirrored : .down
    case .left:
      return mirrored ? .leftMirrored : .left
    }
  }
}

private enum BodyVisionError: Error {
  case invalidFrame
  case nativePixelBufferMissing
  case pixelBufferConversionFailed
  case modelsNotPackaged
  case segmentationMaskMissing
}
