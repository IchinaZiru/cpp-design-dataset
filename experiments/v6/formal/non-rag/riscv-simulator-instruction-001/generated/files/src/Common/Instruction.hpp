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

    InstructionBase() : opcode(0), rs1(0), rs2(0), rd(0), funct3(0), funct7(0), imm(0), inst(0), t(Type::R) {}

    InstructionBase(unsigned inst_val) : inst(inst_val), opcode(get_digits(inst, 6, 0)), rs1(get_digits(inst, 11, 7)), rs2(get_digits(inst, 19, 15)), rd(get_digits(inst, 11, 7)), funct3(get_digits(inst, 14, 12)), funct7(get_digits(inst, 31, 25)), imm(0), t(Type::R) {}

    static InstructionBase nop() {
        return InstructionBase(0b0010011);
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
        if (digit == 0)
            return 0;
        else
            return 0xffffffff << lo;
    }

    bool is_valid(const std::string &key) {
        static const std::string valid_keys[] = {"opcode", "rs1", "rs2", "rd", "funct3", "funct7", "imm", "inst", "t"};
        for (const auto& k : valid_keys) {
            if (k == key)
                return true;
        }
        return false;
    }

    void verify(const std::string &key) {
        if (!is_valid(key))
            throw InvalidAccess();
    }

    void debug() {
        std::cout << "Instruction: " << inst << ", Type: " << t << std::endl;
    }

    bool has_op1() {
        return t != U && t != J;
    }

    bool has_op2() {
        return t == R || t == S || t == B;
    }
};

struct InstructionR : InstructionBase {
    InstructionR(const Instruction &inst) : InstructionBase(inst) {
        rd = get_digits(inst, 11, 7);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct3 = get_digits(inst, 14, 12);
        funct7 = get_digits(inst, 31, 25);
        t = Type::R;
    }
};

struct InstructionI : InstructionBase {
    InstructionI(const Instruction &inst) : InstructionBase(inst) {
        rd = get_digits(inst, 11, 7);
        rs1 = get_digits(inst, 19, 15);
        imm = get_digits(inst, 31, 20);
        funct3 = get_digits(inst, 14, 12);
        t = Type::I;
    }
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase(inst) {
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = (get_digits(inst, 31, 25) << 5) | get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        t = Type::S;
    }
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase(inst) {
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = (get_digits(inst, 31, 31) << 12) | (get_digits(inst, 7, 7) << 11) | (get_digits(inst, 30, 25) << 5) | get_digits(inst, 11, 8);
        funct3 = get_digits(inst, 14, 12);
        t = Type::B;
    }
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase(inst) {
        rd = get_digits(inst, 11, 7);
        imm = get_digits(inst, 31, 12) << 12;
        t = Type::U;
    }
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase(inst) {
        rd = get_digits(inst, 11, 7);
        imm = (get_digits(inst, 31, 31) << 20) | (get_digits(inst, 19, 12) << 1) | (get_digits(inst, 20, 20) << 11) | (get_digits(inst, 30, 21) << 12);
        t = Type::J;
    }
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP