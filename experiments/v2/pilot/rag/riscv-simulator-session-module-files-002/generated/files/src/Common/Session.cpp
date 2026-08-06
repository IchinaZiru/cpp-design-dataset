#include "Session.h"
#include "../Pipeline/Issue.h"
#include "../Pipeline/OoOExecute.h"
#include "../Module/BranchPrediction.h"
#include "Parser.hpp"
#include <fstream>

Session::Session(bool debug) : _debug(debug), rf(), memory(), e(new OoOExecute(this)), i(new Issue(this)), branch(new BranchPrediction()) {
}

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
    std::ifstream in(path);
    load_memory(in);
}

void Session::load_memory(std::istream &in) {
    Parser::parse(in, memory);
}

void Session::load_hex(const char *path) {
    std::ifstream in(path);
    Parser::parse_hex(in, memory);
}

void Session::report(std::ostream &out) {
    out << "Cycle: " << stat.cycle << std::endl;
    i->report(out);
    e->report(out);
}

Session::~Session() {
    delete i;
    delete e;
    delete branch;
}

void Session::debug() {
    std::cout << "Cycle: " << stat.cycle << std::endl;
    i->debug();
    e->debug();
    rf.debug();
}
