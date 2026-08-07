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

    InstructionBase() : opcode(0), rs1(0), rs2(0), rd(0), funct3(0), funct7(0), imm(Immediate()), inst(0), t(R) {}

    InstructionBase(unsigned n) : opcode(get_digits(n, 6, 0)), rs1(get_digits(n, 11, 7)), rs2(get_digits(n, 19, 15)), rd(get_digits(n, 11, 7)), funct3(get_digits(n, 14, 12)), funct7(get_digits(n, 31, 25)), imm(Immediate()), inst(n), t(R) {}

    static InstructionBase nop() {
        return InstructionBase();
    }

    bool is_nop() {
        return opcode == 0 && rs1 == 0 && rs2 == 0 && rd == 0 && funct3 == 0 && funct7 == 0;
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
        if ((digit & (1 << (lo - 1))) != 0) {
            digit |= ~bin_mask(lo);
        }
        return digit;
    }

    bool is_valid(const std::string &key) {
        if (key == "opcode") return true;
        if (key == "rs1" && (t == R || t == I || t == S)) return true;
        if (key == "rs2" && (t == R || t == S || t == B)) return true;
        if (key == "rd" && (t == R || t == I || t == U || t == J)) return true;
        if (key == "funct3" && (t != U && t != J)) return true;
        if (key == "funct7" && t == R) return true;
        if (key == "imm") return true;
        return false;
    }

    void verify(const std::string &key) {
        if (!is_valid(key)) {
            throw InvalidAccess();
        }
    }

    void debug() {
        std::cout << "Instruction Type: " << t << "\n";
        std::cout << "opcode: " << opcode << "\n";
        std::cout << "rs1: " << rs1 << "\n";
        std::cout << "rs2: " << rs2 << "\n";
        std::cout << "rd: " << rd << "\n";
        std::cout << "funct3: " << funct3 << "\n";
        std::cout << "funct7: " << funct7 << "\n";
        std::cout << "imm: " << imm.value() << "\n";
    }

    bool has_op1() {
        return t == R || t == I || t == S;
    }

    bool has_op2() {
        return t == R || t == S || t == B;
    }
};

struct InstructionR : InstructionBase {
    InstructionR(const Instruction &inst) : InstructionBase(inst) {
        t = R;
        rd = get_digits(inst, 11, 7);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct3 = get_digits(inst, 14, 12);
        funct7 = get_digits(inst, 31, 25);
    }
};

struct InstructionI : InstructionBase {
    InstructionI(const Instruction &inst) : InstructionBase(inst) {
        t = I;
        rd = get_digits(inst, 11, 7);
        rs1 = get_digits(inst, 19, 15);
        funct3 = get_digits(inst, 14, 12);
        imm.value() = expand_digit(get_digits(inst, 31, 20), 12);
    }
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase(inst) {
        t = S;
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct3 = get_digits(inst, 14, 12);
        imm.value() = expand_digit((get_digits(inst, 31, 25) << 5) | get_digits(inst, 11, 7), 12);
    }
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase(inst) {
        t = B;
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct3 = get_digits(inst, 14, 12);
        imm.value() = expand_digit((get_digits(inst, 7, 7) << 11) | (get_digits(inst, 30, 25) << 5) | (get_digits(inst, 11, 8) << 1) | get_digits(inst, 31, 31), 13);
    }
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase(inst) {
        t = U;
        rd = get_digits(inst, 11, 7);
        imm.value() = expand_digit(get_digits(inst, 31, 12) << 12, 20);
    }
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase(inst) {
        t = J;
        rd = get_digits(inst, 11, 7);
        imm.value() = expand_digit((get_digits(inst, 31, 31) << 20) | (get_digits(inst, 19, 12) << 12) | (get_digits(inst, 20, 20) << 11) | (get_digits(inst, 30, 21) << 1), 21);
    }
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP