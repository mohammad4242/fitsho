require "json"

package = JSON.parse(File.read(File.join(__dir__, "package.json")))

Pod::Spec.new do |s|
  s.name         = "FiticianBodyVision"
  s.version      = package["version"]
  s.summary      = "Private on-device body pose and segmentation for Fitician"
  s.description  = "Nitro body vision module backed by MediaPipe Tasks Vision"
  s.homepage     = "https://github.com/mohammad4242/fitsho"
  s.license      = { :type => "UNLICENSED" }
  s.author       = { "Fitician" => "engineering@fitician.app" }
  s.source       = { :git => "https://github.com/mohammad4242/fitsho.git", :branch => "main" }

  s.platforms    = { :ios => min_ios_version_supported }
  s.source_files = [
    "ios/**/*.{swift,m,mm}",
  ]
  s.resource_bundles = {
    "FiticianBodyVisionResources" => [
      "android/src/main/assets/body_vision/pose_landmarker_lite.task",
      "android/src/main/assets/body_vision/selfie_segmenter.tflite",
    ],
  }
  s.frameworks = ["AVFoundation", "CoreImage", "CoreVideo"]

  load "nitrogen/generated/ios/FiticianBodyVision+autolinking.rb"
  add_nitrogen_files(s)

  s.dependency "React-jsi"
  s.dependency "React-callinvoker"
  s.dependency "VisionCamera"
  s.dependency "MediaPipeTasksVision", "~> 0.10.35"
  install_modules_dependencies(s)
end
