#include <type_traits>

#if defined(__has_include)
#if __has_include(<charconv>)
#include <charconv>
#define FIXTURE_HAS_CHARCONV 1
#endif
#endif

template <typename T>
inline constexpr bool fixture_use_charconv =
#if defined(FIXTURE_HAS_CHARCONV)
    std::is_floating_point_v<T> ||
#endif
    std::is_integral_v<T>;

template <typename T>
bool fixture_parse(T value) {
#if defined(FIXTURE_HAS_CHARCONV)
    if constexpr (fixture_use_charconv<T>) {
        return value != T{};
    } else
#endif
    {
        return false;
    }
}
