#include "Session.h"
#include "../Pipeline/Issue.h"
#include "../Pipeline/OoOExecute.h"
#include "../Module/BranchPrediction.h"
#include "Parser.hpp"
#include <thread>
#include <fstream>
#include <random>
#include <functional>

Session::Session(bool debug) : _debug(debug), rf(), memory(), e(new OoOExecute()), i(new Issue()), branch(new BranchPrediction()) {}

void Session::tick() {
    stat.cycle++;
    i->update();
    e->update();
    if (_debug) {
        debug();
    }
    i->tick();
    e->tick();
    rf.tick();
}

void Session::load_memory(const char *path) {
    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open memory file.");
    }
    memory.load(file);
}

void Session::load_memory(std::istream &in) {
    memory.load(in);
}

void Session::load_hex(const char *path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open hex file.");
    }
    memory.load_hex(file);
}

void Session::report(std::ostream& out) {
    out << "Cycle Count: " << stat.cycle << std::endl;
    rf.report(out);
    memory.report(out);
    i->report(out);
    e->report(out);
    branch->report(out);
}

Session::~Session() {
    delete e;
    delete i;
    delete branch;
}

void Session::debug() {
    rf.debug();
    memory.debug();
    i->debug();
    e->debug();
    branch->debug();
}
