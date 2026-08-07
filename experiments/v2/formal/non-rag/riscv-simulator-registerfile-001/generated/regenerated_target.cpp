class RegisterFile { // : public Tickable {
    static const int REG_NUM = 32;
public:
    Immediate prev[REG_NUM];
    Immediate next[REG_NUM];

    RegisterFile() {
        for (int i = 0; i < REG_NUM; ++i) {
            prev[i] = 0;
            next[i] = 0;
        }
    }

    void tick() {
        for (int i = 1; i < REG_NUM; ++i) { // Skip register 0
            prev[i] = next[i];
        }
    }

    Immediate read(int id) {
        if (id == 0) return 0;
        return prev[id];
    }

    void write(int id, Immediate val) {
        if (id != 0) {
            next[id] = val;
        }
    }

    void debug() {
        for (int i = 0; i < REG_NUM; ++i) {
            std::cout << "Register[" << std::setw(2) << i << "]: "
                      << "prev=" << std::setw(16) << prev[i] << ", "
                      << "next=" << std::setw(16) << next[i] << std::endl;
        }
    }
};