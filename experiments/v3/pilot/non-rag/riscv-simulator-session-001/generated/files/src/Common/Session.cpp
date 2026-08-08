#include "Session.h"
#include "../Pipeline/Issue.h"
#include "../Pipeline/OoOExecute.h"
#include "../Module/BranchPrediction.h"
#include "Parser.hpp"
#include <thread>
#include <fstream>
#include <random>
#include <functional>

Session::Session(bool debug)
    : _debug(debug), rf(), memory(), e(new OoOExecute()), i(new Issue()), branch(new BranchPrediction()) {
}

void Session::tick() {
    i->issue();
    e->execute();
    stat.cycle++;
    if (_debug) {
        debug();
    }
}

void Session::load_memory(const char *path) {
    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open memory file.");
    }
    load_memory(file);
}

void Session::load_memory(std::istream &in) {
    in.read(reinterpret_cast<char*>(memory.data()), memory.size());
}

void Session::load_hex(const char *path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open hex file.");
    }
    Parser parser;
    parser.parse_hex(file, memory);
}

void Session::report(std::ostream& out) {
    out << "Simulation Report:\n";
    out << "Cycles: " << stat.cycle << "\n";
    // Additional report details can be added here.
}

Session::~Session() {
    delete e;
    delete i;
    delete branch;
}

void Session::debug() {
    std::cout << "Cycle: " << stat.cycle << "\n";
    // Debug information for each stage can be added here.
}
