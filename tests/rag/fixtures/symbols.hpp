#pragma once

#define CPP_RAG_LIMIT 64
#define CPP_RAG_DOUBLE(value) \
    ((value) * 2)

namespace fixture {

using Size = unsigned long;
typedef unsigned int LegacyId;

enum class State {
    Idle,
    Running,
};

struct Base {
    virtual ~Base() = default;
    virtual int id() const noexcept = 0;
};

template <class T>
class Widget : public Base {
public:
    struct Nested {
        T item;
    };

    Widget() noexcept;
    ~Widget() override;

    int id() const noexcept override;
    int value() const noexcept;
    int value(int offset) &;
    Widget& operator=(const Widget& other);

private:
    T value_{};
};

/**
 * @brief A fixture function whose comment must remain attached.
 */
int documented(Size input) noexcept;

int overloaded(int value);
int overloaded(double value);
constexpr int kDefaultValue = 7;

}  // namespace fixture
