template<typename T>
class Register { // : public Tickable {
public:
    T prev, next;

    bool _stall;

    Register() : prev((T) 0), next((T) 0), _stall(false) {}

    Register(T d) : prev(d), next(d), _stall(false) {}

    T read() const {
        return prev;
    }

    T current() const {
        return next;
    }

    void write(const T &t) {
        next = t;
    }

    void tick() {
        if (!_stall) {
            prev = next;
        }
    }

    void stall(bool stall) {
        _stall = stall;
    }

    operator T() const {
        return prev;
    }

    void operator=(T next) {
        this->next = next;
    }
};