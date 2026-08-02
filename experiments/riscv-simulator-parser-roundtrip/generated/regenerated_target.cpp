#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include "Memory.hpp"

class Parser {
public:
    static unsigned parse_hex(const std::string &hex) {
        char *end;
        unsigned value = strtoul(hex.c_str(), &end, 16);
        if (*end != '\0') {
            std::cerr << "Invalid hex string: " << hex << std::endl;
        }
        return value;
    }

    static void parse(std::istream &in, Memory &mem) {
        if (!in.good()) {
            std::cerr << "Input stream is not valid." << std::endl;
            return;
        }

        unsigned base_address = 0;
        std::string line;
        while (std::getline(in, line)) {
            if (line.empty()) continue;

            if (line[0] == '@') {
                base_address = parse_hex(line.substr(1));
            } else {
                std::istringstream iss(line);
                std::string hex_word;
                while (iss >> hex_word) {
                    unsigned value = parse_hex(hex_word);
                    mem.write_word(base_address, value);
                    ++base_address;
                }
            }
        }
    }

    static void parse_hex(std::istream &in, Memory &mem) {
        if (!in.good()) {
            std::cerr << "Input stream is not valid." << std::endl;
            return;
        }

        unsigned base_address = 0;
        std::string hex_word;
        while (in >> hex_word) {
            unsigned value = parse_hex(hex_word);
            mem.write_word(base_address, value);
            ++base_address;
        }
    }
};