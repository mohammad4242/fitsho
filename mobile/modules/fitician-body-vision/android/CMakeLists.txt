project(FiticianBodyVision)
cmake_minimum_required(VERSION 3.9.0)

set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_CXX_STANDARD 20)

add_library(FiticianBodyVision SHARED
  src/main/cpp/cpp-adapter.cpp
)

include(${CMAKE_SOURCE_DIR}/../nitrogen/generated/android/FiticianBodyVision+autolinking.cmake)

find_library(LOG_LIB log)
find_package(react-native-nitro-modules REQUIRED)
find_package(react-native-vision-camera REQUIRED)
find_package(react-native-worklets REQUIRED)

target_link_libraries(
  FiticianBodyVision
  ${LOG_LIB}
  android
  react-native-nitro-modules::NitroModules
  react-native-vision-camera::VisionCamera
  react-native-worklets::worklets
)
