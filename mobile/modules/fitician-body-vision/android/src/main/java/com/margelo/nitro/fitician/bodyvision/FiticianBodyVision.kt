package com.margelo.nitro.fitician.bodyvision

import androidx.annotation.CallSuper
import androidx.annotation.Keep
import com.facebook.proguard.annotations.DoNotStrip
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.framework.image.ByteBufferExtractor
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.imagesegmenter.ImageSegmenter
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker
import com.margelo.nitro.NitroModules
import com.margelo.nitro.camera.HybridFrameSpec
import com.margelo.nitro.camera.extensions.toBitmap
import com.margelo.nitro.camera.public.NativeFrame
import com.margelo.nitro.core.ArrayBuffer
import java.io.IOException
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicLong

@Keep
@DoNotStrip
class FiticianBodyVision : HybridFiticianBodyVisionSpec() {
  private val processedFrameCount = AtomicLong(0)
  private val droppedFrameCount = AtomicLong(0)
  private val totalFrameDurationNanos = AtomicLong(0)
  private val maxFrameDurationNanos = AtomicLong(0)

  override val contractVersion: String = CONTRACT_VERSION

  override val modelStatus: String
    get() = if (modelsAvailable()) MODEL_STATUS_READY else MODEL_STATUS_NOT_PACKAGED

  override fun process(frame: HybridFrameSpec): NativeBodyVisionResult {
    check(modelsAvailable()) { "BODY_VISION_MODELS_NOT_PACKAGED" }
    val nativeFrame = frame as? NativeFrame
      ?: throw IllegalArgumentException("The given Frame was not a native VisionCamera frame")
    val startedAt = System.nanoTime()
    val bitmap = nativeFrame.image.toBitmap(frame.orientation, frame.isMirrored)

    return try {
      val mpImage = BitmapImageBuilder(bitmap).build()
      val poseResult = poseLandmarker.value.detect(mpImage)
      val segmentationResult = imageSegmenter.value.segment(mpImage)
      val segmentationMask = segmentationResult.categoryMask().orElse(null)
        ?: throw IllegalStateException("MediaPipe returned no segmentation mask")
      val maskBytes = ByteBufferExtractor.extract(segmentationMask)
      val elapsedNanos = System.nanoTime() - startedAt
      processedFrameCount.incrementAndGet()
      totalFrameDurationNanos.addAndGet(elapsedNanos)
      updateMaximum(maxFrameDurationNanos, elapsedNanos)

      NativeBodyVisionResult(
        landmarks = poseResult.landmarks().map { pose ->
          pose.map { landmark ->
            NativeBodyLandmark(
              x = landmark.x().toDouble(),
              y = landmark.y().toDouble(),
              z = landmark.z().toDouble(),
              visibility = landmark.visibility().orElse(0f).toDouble(),
            )
          }.toTypedArray()
        }.toTypedArray(),
        mask = NativeBodyVisionMask(
          width = segmentationMask.width.toDouble(),
          height = segmentationMask.height.toDouble(),
          values = ArrayBuffer.wrap(copyBuffer(maskBytes)),
        ),
        frame = NativeBodyVisionFrame(
          width = frame.width,
          height = frame.height,
          timestamp = frame.timestamp,
        ),
      )
    } finally {
      bitmap.recycle()
    }
  }

  override fun recordDroppedFrame() {
    droppedFrameCount.incrementAndGet()
  }

  override fun benchmark(): NativeBodyVisionBenchmark {
    val processed = processedFrameCount.get()
    val totalNanos = totalFrameDurationNanos.get()
    return NativeBodyVisionBenchmark(
      frameCount = processed.toDouble() + droppedFrameCount.get().toDouble(),
      processedFrameCount = processed.toDouble(),
      droppedFrameCount = droppedFrameCount.get().toDouble(),
      averageFrameDurationMs = if (processed == 0L) 0.0 else totalNanos / processed / NANOS_PER_MILLISECOND,
      maxFrameDurationMs = maxFrameDurationNanos.get() / NANOS_PER_MILLISECOND,
      modelStatus = modelStatus,
    )
  }

  @CallSuper
  override fun dispose() {
    if (poseLandmarker.isInitialized()) poseLandmarker.value.close()
    if (imageSegmenter.isInitialized()) imageSegmenter.value.close()
    super.dispose()
  }

  private val poseLandmarker: Lazy<PoseLandmarker> = lazy {
    val options = PoseLandmarker.PoseLandmarkerOptions.builder()
      .setBaseOptions(BaseOptions.builder().setModelAssetPath(POSE_MODEL_ASSET).build())
      .setRunningMode(RunningMode.IMAGE)
      .setMinPoseDetectionConfidence(MIN_POSE_CONFIDENCE)
      .setMinTrackingConfidence(MIN_POSE_CONFIDENCE)
      .setMinPosePresenceConfidence(MIN_POSE_CONFIDENCE)
      .build()
    PoseLandmarker.createFromOptions(applicationContext, options)
  }

  private val imageSegmenter: Lazy<ImageSegmenter> = lazy {
    val options = ImageSegmenter.ImageSegmenterOptions.builder()
      .setBaseOptions(BaseOptions.builder().setModelAssetPath(SEGMENTATION_MODEL_ASSET).build())
      .setRunningMode(RunningMode.IMAGE)
      .setOutputCategoryMask(true)
      .setOutputConfidenceMasks(false)
      .build()
    ImageSegmenter.createFromOptions(applicationContext, options)
  }

  private val applicationContext
    get() = NitroModules.applicationContext
      ?: throw IllegalStateException("No React application context is available")

  private fun modelsAvailable(): Boolean {
    return assetExists(POSE_MODEL_ASSET) && assetExists(SEGMENTATION_MODEL_ASSET)
  }

  private fun assetExists(path: String): Boolean {
    return try {
      applicationContext.assets.open(path).use { }
      true
    } catch (_: IOException) {
      false
    }
  }

  private fun copyBuffer(source: ByteBuffer): ByteBuffer {
    val readable = source.duplicate()
    readable.rewind()
    val copy = ByteBuffer.allocateDirect(readable.remaining())
    copy.put(readable)
    copy.flip()
    return copy
  }

  private fun updateMaximum(target: AtomicLong, candidate: Long) {
    while (true) {
      val current = target.get()
      if (candidate <= current || target.compareAndSet(current, candidate)) return
    }
  }

  private companion object {
    const val CONTRACT_VERSION = "1.0"
    const val MODEL_STATUS_READY = "ready"
    const val MODEL_STATUS_NOT_PACKAGED = "not-packaged"
    const val POSE_MODEL_ASSET = "body_vision/pose_landmarker_lite.task"
    const val SEGMENTATION_MODEL_ASSET = "body_vision/selfie_segmenter.tflite"
    const val MIN_POSE_CONFIDENCE = 0.5f
    const val NANOS_PER_MILLISECOND = 1_000_000.0
  }
}
