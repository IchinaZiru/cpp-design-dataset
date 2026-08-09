//
// Created by Alex Chi on 2019-07-01.
//

#ifndef RISCV_SIMULATOR_INSTRUCTION_HPP
#define RISCV_SIMULATOR_INSTRUCTION_HPP

#include <utility>
#include "Common.h"
#include <string>
#include <iostream>

using Instruction = unsigned int;

struct InstructionBase {
    class InvalidAccess {
    };

    InstructionBase() : opcode(0), rs1(0), rs2(0), rd(0), funct3(0), funct7(0), imm(Immediate()), inst(0), t(Type::R) {}

    InstructionBase(unsigned i) : inst(i), opcode(get_digits(i, 6, 0)), rs1(get_digits(i, 11, 7)), rs2(get_digits(i, 19, 15)), rd(get_digits(i, 11, 7)), funct3(get_digits(i, 14, 12)), funct7(get_digits(i, 31, 25)), imm(Immediate()), t(Type::R) {
        if (opcode == 0b0110011) {
            t = Type::R;
        } else if ((opcode & 0b0010011) == 0b0010011 || opcode == 0b1100111) {
            t = Type::I;
        } else if (opcode == 0b0100011) {
            t = Type::S;
        } else if ((opcode & 0b0000011) == 0b0000011 || opcode == 0b1100011) {
            t = Type::I;
        } else if (opcode == 0b1100011) {
            t = Type::B;
        } else if (opcode == 0x37 || opcode == 0x17) {
            t = Type::U;
        } else if (opcode == 0x6f) {
            t = Type::J;
        }
    }

    static InstructionBase nop() {
        return InstructionBase(0b0010011);
    }

    bool is_nop() {
        return inst == -1;
    }

    unsigned opcode, rs1, rs2, rd, funct3, funct7;
    Immediate imm;
    Instruction inst;
    enum Type {
        R, I, S, B, U, J
    } t;

    static constexpr unsigned int bin_mask(int digits) {
        return (1 << digits) - 1;
    }

    static unsigned int get_digits(unsigned int n, int hi, int lo) {
        return (n >> lo) & bin_mask(hi - lo + 1);
    }

    static unsigned int expand_digit(unsigned int digit, int lo) {
        return digit ? (0xffffffff << lo) : 0;
    }

    bool is_valid(const std::string &key) {
        if (key == "opcode") return true;
        if (key == "rs1" && (t == R || t == I || t == S)) return true;
        if (key == "rs2" && (t == R || t == S || t == B)) return true;
        if (key == "rd" && (t == R || t == I || t == U || t == J)) return true;
        if (key == "funct3" && (t == R || t == I || t == S || t == B)) return true;
        if (key == "funct7" && t == R) return true;
        if (key == "imm") return true;
        return false;
    }

    void verify(const std::string &key) {
        if (!is_valid(key)) throw InvalidAccess();
    }

    void debug() {
        switch (opcode) {
            case 0b0110011: std::cout << "R-type instruction"; break;
            case 0b0010011: std::cout << "I-type instruction"; break;
            case 0b0100011: std::cout << "S-type instruction"; break;
            case 0b1100011: std::cout << "B-type instruction"; break;
            case 0x37: case 0x17: std::cout << "U-type instruction"; break;
            case 0x6f: std::cout << "J-type instruction"; break;
            default: std::cout << "Unknown instruction"; break;
        }
        std::cout << " (opcode: " << opcode << ")\n";
    }

    bool has_op1() {
        return t != U && t != J;
    }

    bool has_op2() {
        return t == R || t == S || t == B;
    }
};

struct InstructionR : InstructionBase {
    InstructionR(const Instruction &inst) : InstructionBase(inst) {}
};

struct InstructionI : InstructionBase {
    InstructionI(const Instruction &inst) : InstructionBase(inst) {}
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase(inst) {}
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase(inst) {}
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase(inst) {}
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase(inst) {}
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP