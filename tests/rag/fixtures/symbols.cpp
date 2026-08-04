#include "symbols.hpp"

namespace fixture {

template <class T>
Widget<T>::Widget() noexcept = default;

template <class T>
Widget<T>::~Widget() = default;

template <class T>
int Widget<T>::id() const noexcept {
    return static_cast<int>(value_);
}

template <class T>
int Widget<T>::value() const noexcept {
    return static_cast<int>(value_);
}

template <class T>
int Widget<T>::value(int offset) & {
    return static_cast<int>(value_) + offset;
}

template <class T>
Widget<T>& Widget<T>::operator=(const Widget& other) = default;

int documented(Size input) noexcept {
    return static_cast<int>(input);
}

int overloaded(int value) {
    return value;
}

int overloaded(double value) {
    return static_cast<int>(value);
}

}  // namespace fixture
