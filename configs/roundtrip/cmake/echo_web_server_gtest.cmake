# External evaluation harness hook.
# The upstream project calls gtest_discover_tests() from subdirectories
# but does not include CMake's GoogleTest module itself.
include(GoogleTest)
