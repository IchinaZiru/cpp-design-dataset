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
        for (int i = 0; i < REG_NUM; ++i) {
            prev[i] = next[i];
        }
    }

    Immediate read(int id) {
        if (id == 0) return 0;
        return prev[id];
    }

    void write(int id, Immediate val) {
        if (id > 0 && id < REG_NUM) {
            next[id] = val;
        }
    }

    void debug() {
        for (int i = 0; i < REG_NUM; ++i) {
            std::cout << "Register[" << std::setw(2) << i << "]: ";
            debug_immediate(next[i]);
            std::cout << std::endl;
        }
    }
};