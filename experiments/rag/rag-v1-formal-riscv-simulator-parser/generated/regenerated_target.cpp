#include <iostream>
#include <sstream>
#include <string>
#include <cstdlib>

class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        char *end;
        return static_cast<unsigned>(std::strtol(hex.c_str(), &end, 16));
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in.good()) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string line;
        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                std::istringstream iss(line);
                std::string hex_value;
                unsigned addr = base_addr;
                while (iss >> hex_value) {
                    mem.write(addr++, parse_hex(hex_value));
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in.good()) {
            std::cerr << "Invalid input stream" << std::endl;
            return;
        }

        unsigned base_addr = 0;
        std::string line;
        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_addr = parse_hex(line.substr(1));
            } else {
                for (size_t i = 0; i < line.length(); i += 8) {
                    std::string hex_value = line.substr(i, 8);
                    mem.write(base_addr++, parse_hex(hex_value));
                }
            }
        }
    }
};