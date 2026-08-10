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
        memcpy(prev, next, sizeof(prev));
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
        static std::vector<std::string> rf_name = {"0", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"};
        for (int i = 0; i < REG_NUM; i += 4) {
            std::cout << std::setw(20) << rf_name[i]   << ": ";
            debug_immediate(next[i], 11);
            if (i + 1 < REG_NUM) {
                std::cout << std::setw(20) << rf_name[i + 1] << ": ";
                debug_immediate(next[i + 1], 11);
            }
            if (i + 2 < REG_NUM) {
                std::cout << std::setw(20) << rf_name[i + 2] << ": ";
                debug_immediate(next[i + 2], 11);
            }
            if (i + 3 < REG_NUM) {
                std::cout << std::setw(20) << rf_name[i + 3] << ": ";
                debug_immediate(next[i + 3], 11);
            }
            std::cout << std::endl;
        }
    }
};