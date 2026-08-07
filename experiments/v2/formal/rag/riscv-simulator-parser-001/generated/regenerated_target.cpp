class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        char* end;
        return static_cast<unsigned>(strtol(hex.c_str(), &end, 16));
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned base_address = 0;
        std::string line;

        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_address = parse_hex(line.substr(1));
            } else {
                std::stringstream ss(line);
                std::string hex_value;
                while (ss >> hex_value) {
                    unsigned value = parse_hex(hex_value);
                    mem[base_address++] = static_cast<char>(value & 0xFF);
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned base_address = 0;
        std::string hex_value;

        while (in >> hex_value) {
            unsigned value = parse_hex(hex_value);
            mem.write_word(base_address++, static_cast<char>(value & 0xFF));
        }
    }
};