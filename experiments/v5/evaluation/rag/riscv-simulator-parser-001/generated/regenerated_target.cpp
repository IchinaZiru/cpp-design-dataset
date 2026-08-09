class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        if (hex.empty()) {
            return 0;
        }
        char *endptr;
        unsigned result = static_cast<unsigned>(std::strtol(hex.c_str(), &endptr, 16));
        if (*endptr != '\0') {
            std::cerr << "Invalid hex string: " << hex << std::endl;
        }
        return result;
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Input stream is invalid." << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string line;
        while (std::getline(in, line)) {
            if (line.empty()) {
                continue;
            }
            if (line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                std::stringstream ss(line);
                std::string hex_byte;
                while (ss >> hex_byte) {
                    if (!hex_byte.empty()) {
                        unsigned byte_value = parse_hex(hex_byte);
                        if (mem.check_addr(base_addr)) {
                            mem[base_addr++] = static_cast<unsigned char>(byte_value);
                        }
                    }
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Input stream is invalid." << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string hex_word;
        while (in >> hex_word) {
            if (!hex_word.empty()) {
                unsigned word_value = parse_hex(hex_word);
                if (mem.check_addr(base_addr)) {
                    mem.write_word(base_addr, static_cast<Immediate>(word_value));
                    base_addr += 4;
                }
            }
        }
    }
};