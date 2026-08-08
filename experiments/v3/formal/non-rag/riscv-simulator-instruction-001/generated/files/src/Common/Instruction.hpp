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

    InstructionBase(unsigned inst) : inst(inst), t(static_cast<Type>(get_digits(inst, 6, 2))) {
        opcode = get_digits(inst, 6, 0);
        rs1 = get_digits(inst, 11, 7);
        rs2 = get_digits(inst, 19, 15);
        rd = get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        funct7 = get_digits(inst, 31, 25);
        imm = 0;
    }

    static InstructionBase nop() {
        return InstructionBase(0x00000013); // NOP in RISC-V is addi x0, x0, 0
    }

    bool is_nop() {
        return inst == 0x00000013;
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
        if ((digit & (1 << (lo - 1))) != 0)
            return digit | ~bin_mask(lo);
        else
            return digit;
    }

    bool is_valid(const std::string &key) {
        switch (t) {
            case R:
                return key == "opcode" || key == "rs1" || key == "rs2" || key == "rd" || key == "funct3" || key == "funct7";
            case I:
                return key == "opcode" || key == "rs1" || key == "rd" || key == "funct3" || key == "imm";
            case S:
                return key == "opcode" || key == "rs1" || key == "rs2" || key == "funct3" || key == "imm";
            case B:
                return key == "opcode" || key == "rs1" || key == "rs2" || key == "funct3" || key == "imm";
            case U:
                return key == "opcode" || key == "rd" || key == "imm";
            case J:
                return key == "opcode" || key == "rd" || key == "imm";
            default:
                return false;
        }
    }

    void verify(const std::string &key) {
        if (!is_valid(key))
            throw InvalidAccess();
    }

    void debug() {
        std::cout << "Instruction: 0x" << std::hex << inst << std::dec << "\n";
        std::cout << "Type: " << static_cast<int>(t) << "\n";
        std::cout << "Opcode: " << opcode << "\n";
        std::cout << "Rs1: " << rs1 << "\n";
        std::cout << "Rs2: " << rs2 << "\n";
        std::cout << "Rd: " << rd << "\n";
        std::cout << "Funct3: " << funct3 << "\n";
        std::cout << "Funct7: " << funct7 << "\n";
        std::cout << "Imm: " << imm << "\n";
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
    InstructionI(const Instruction &inst) : InstructionBase(inst) {
        imm = expand_digit(get_digits(inst, 31, 20), 12);
    }
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase(inst) {
        unsigned imm_low = get_digits(inst, 11, 7);
        unsigned imm_high = get_digits(inst, 31, 25);
        imm = expand_digit((imm_high << 5) | imm_low, 12);
    }
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase(inst) {
        unsigned imm_low = get_digits(inst, 7, 7);
        unsigned imm_mid = get_digits(inst, 12, 8);
        unsigned imm_high = get_digits(inst, 30, 25);
        unsigned imm_sign = get_digits(inst, 31, 31);
        imm = expand_digit((imm_sign << 12) | (imm_high << 5) | (imm_mid << 1) | imm_low, 13);
    }
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase(inst) {
        imm = get_digits(inst, 31, 12) << 12;
    }
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase(inst) {
        unsigned imm_low = get_digits(inst, 20, 20);
        unsigned imm_mid = get_digits(inst, 30, 21);
        unsigned imm_high = get_digits(inst, 19, 12);
        unsigned imm_sign = get_digits(inst, 31, 31);
        imm = expand_digit((imm_sign << 20) | (imm_high << 1) | imm_mid | (imm_low << 11), 21);
    }
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP