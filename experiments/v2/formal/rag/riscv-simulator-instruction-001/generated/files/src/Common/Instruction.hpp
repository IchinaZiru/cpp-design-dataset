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

    InstructionBase(unsigned) : opcode(0b0010011), rs1(0), rs2(0), rd(0), funct3(0), funct7(0), imm(0), inst(0), t(I) {}

    static InstructionBase nop() {
        InstructionBase ib;
        ib.inst = -1;
        return ib;
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
        if (digit == 0)
            return 0;
        else
            return ((-1 << lo) | digit);
    }

    bool is_valid(const std::string &key) {
        // Placeholder for actual validation logic
        return true;
    }

    void verify(const std::string &key) {
        if (!is_valid(key))
            throw InvalidAccess();
    }

    void debug() {
        std::cout << "Instruction: " << inst << ", Opcode: " << opcode << ", Funct3: " << funct3 << std::endl;
    }

    bool has_op1() {
        return t == R || t == I || t == S || t == B;
    }

    bool has_op2() {
        return t == R || t == S || t == B;
    }
};

struct InstructionR : InstructionBase {
    InstructionR(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct7 = get_digits(inst, 31, 25);
        this->inst = inst;
        t = R;
    }
};

struct InstructionI : InstructionBase {
    InstructionI(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        imm = get_digits(inst, 30, 20) | expand_digit(get_digits(inst, 31, 31), 11);
        this->inst = inst;
        t = I;
    }
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = get_digits(inst, 11, 7) | (get_digits(inst, 30, 25) << 5) | expand_digit(get_digits(inst, 31, 31), 11);
        this->inst = inst;
        t = S;
    }
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = (get_digits(inst, 11, 8) << 1) | (get_digits(inst, 30, 25) << 5) | (get_digits(inst, 7, 7) << 11) | expand_digit(get_digits(inst, 31, 31), 12);
        this->inst = inst;
        t = B;
    }
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        imm = (get_digits(inst, 19, 12) << 12) | (get_digits(inst, 30, 20) << 20) | (get_digits(inst, 31, 31) << 31);
        this->inst = inst;
        t = U;
    }
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase() {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        imm = (get_digits(inst, 30, 21) << 1) | (get_digits(inst, 20, 20) << 11) | (get_digits(inst, 19, 12) << 12) | expand_digit(get_digits(inst, 31, 31), 20);
        this->inst = inst;
        t = J;
    }
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP