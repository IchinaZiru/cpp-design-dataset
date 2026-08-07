class RegisterFile { // : public Tickable {
    static const int REG_NUM = 32;
public:
    Immediate prev[REG_NUM];
    Immediate next[REG_NUM];

    RegisterFile() {
        memset(prev, 0, sizeof(prev));
        memset(next, 0, sizeof(next));
    }

    void tick() {
        memcpy(prev, next, sizeof(next));
    }

    Immediate read(int id) {
        if (id == 0) {
            return 0;
        }
        return prev[id];
    }

    void write(int id, Immediate val) {
        next[id] = val;
    }

    void debug() {
        for (int i = 0; i < REG_NUM; ++i) {
            std::cout << "x" << std::setw(2) << std::setfill('0') << i << ": ";
            debug_immediate(next[i]);
            std::cout << std::endl;
        }
    }
};