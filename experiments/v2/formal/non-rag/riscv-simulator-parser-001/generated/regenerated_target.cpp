class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        char *end;
        unsigned long value = strtoul(hex.c_str(), &end, 16);
        if (*end != '\0') {
            std::cerr << "Invalid hex string: " << hex << std::endl;
        }
        return static_cast<unsigned>(value);
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        std::string line;
        unsigned base_addr = 0;

        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                std::istringstream iss(line);
                std::string hex;
                while (iss >> hex) {
                    mem.write(base_addr++, parse_hex(hex));
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string hex;

        while (in >> hex) {
            mem.write(base_addr, parse_hex(hex));
            base_addr += 4; // Assuming each word is 4 bytes
        }
    }
};