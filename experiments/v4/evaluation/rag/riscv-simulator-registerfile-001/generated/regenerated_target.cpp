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
        std::memcpy(prev, next, sizeof(prev));
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
        const char* rf_name[REG_NUM] = {
            "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
            "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
            "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
            "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"
        };

        for (int i = 0; i < 4; ++i) {
            for (int j = i * 8; j < i * 8 + 8; ++j) {
                std::cout << "#" << j << "(" << rf_name[j] << ") ";
            }
            std::cout << std::endl;
            for (int j = i * 8; j < i * 8 + 8; ++j) {
                debug_immediate(next[j], 11);
            }
            std::cout << std::endl;
        }
    }
};