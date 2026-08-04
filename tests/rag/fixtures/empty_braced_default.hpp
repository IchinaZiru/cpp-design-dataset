#pragma once

#include <initializer_list>
#include <string_view>

namespace fixture {

void EmptyBracedDefault(
    std::initializer_list<std::string_view> required_fields = {});

}  // namespace fixture
