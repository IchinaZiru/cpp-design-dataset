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

    InstructionBase() : opcode(0), rs1(0), rs2(0), rd(0), funct3(0), funct7(0), imm(0), inst(0), t(R) {}

    InstructionBase(unsigned i) : inst(i), opcode(get_digits(i, 6, 0)), rs1(get_digits(i, 11, 7)), rs2(get_digits(i, 19, 15)), rd(get_digits(i, 11, 7)), funct3(get_digits(i, 14, 12)), funct7(get_digits(i, 31, 25)), imm(0), t(static_cast<Type>(get_digits(i, 6, 0))) {
        switch (t) {
            case R:
                rd = get_digits(i, 19, 15);
                break;
            case I:
                imm = Immediate(get_digits(i, 31, 20));
                rd = get_digits(i, 11, 7);
                break;
            case S:
                imm = Immediate((get_digits(i, 31, 25) << 5) | get_digits(i, 11, 7));
                rs2 = get_digits(i, 24, 20);
                rs1 = get_digits(i, 19, 15);
                break;
            case B:
                imm = Immediate((get_digits(i, 31, 31) << 12) | (get_digits(i, 7, 7) << 11) | (get_digits(i, 12, 8) << 1) | (get_digits(i, 6, 5) << 5));
                rs2 = get_digits(i, 24, 20);
                rs1 = get_digits(i, 19, 15);
                break;
            case U:
                imm = Immediate(get_digits(i, 31, 12) << 12);
                rd = get_digits(i, 11, 7);
                break;
            case J:
                imm = Immediate((get_digits(i, 31, 31) << 20) | (get_digits(i, 19, 12) << 1) | (get_digits(i, 20, 20) << 11) | (get_digits(i, 30, 21) << 12));
                rd = get_digits(i, 11, 7);
                break;
        }
    }

    static InstructionBase nop() {
        return InstructionBase(0);
    }

    bool is_nop() {
        return inst == 0;
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
        if (key == "rs1" && (t == R || t == I || t == S || t == B)) return true;
        if (key == "rs2" && (t == R || t == S || t == B)) return true;
        if (key == "rd" && (t == R || t == I || t == U || t == J)) return true;
        if (key == "funct3") return true;
        if (key == "funct7" && t == R) return true;
        if (key == "imm") return true;
        return false;
    }

    void verify(const std::string &key) {
        if (!is_valid(key)) throw InvalidAccess();
    }

    void debug() {
        switch (t) {
            case R:
                std::cout << "R-type: rd=" << rd << ", rs1=" << rs1 << ", rs2=" << rs2 << ", funct3=" << funct3 << ", funct7=" << funct7 << std::endl;
                break;
            case I:
                std::cout << "I-type: rd=" << rd << ", rs1=" << rs1 << ", imm=" << imm.value() << ", funct3=" << funct3 << std::endl;
                break;
            case S:
                std::cout << "S-type: rs2=" << rs2 << ", rs1=" << rs1 << ", imm=" << imm.value() << ", funct3=" << funct3 << std::endl;
                break;
            case B:
                std::cout << "B-type: rs2=" << rs2 << ", rs1=" << rs1 << ", imm=" << imm.value() << ", funct3=" << funct3 << std::endl;
                break;
            case U:
                std::cout << "U-type: rd=" << rd << ", imm=" << imm.value() << std::endl;
                break;
            case J:
                std::cout << "J-type: rd=" << rd << ", imm=" << imm.value() << std::endl;
                break;
        }
    }

    bool has_op1() {
        return t == R || t == I || t == S || t == B;
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