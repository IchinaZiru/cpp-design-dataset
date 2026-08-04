#include "project/widget.hpp"
#include <vector>

#define PROJECT_LIMIT 8

namespace fixture {

enum class Mode {
    Ready,
    Busy,
};

constexpr int DefaultCount = PROJECT_LIMIT;

struct Base {};

struct Outer : public Base {
    struct Nested {};
    using Alias = Nested;

    Mode mode = Mode::Ready;

    void Run(ProjectType& value) {
        helper(value);
        fixture::qualified(value);
        value.Process(DefaultCount);
        get();
        auto* created = new ProjectType();
        Outer::Nested nested_value;
        Mode other = Mode::Busy;
        std::vector<int> local;
        delete created;
    }
};

}  // namespace fixture
