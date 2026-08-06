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

    InstructionBase(unsigned n) : opcode(get_digits(n, 6, 0)), rs1(get_digits(n, 11, 7)), rs2(get_digits(n, 19, 15)), rd(get_digits(n, 11, 7)), funct3(get_digits(n, 14, 12)), funct7(get_digits(n, 31, 25)), imm(Immediate()), inst(n), t(R) {
        if (opcode == 0x33) {
            t = R;
        } else if ((opcode & 0x3) == 0x3) {
            switch (funct3) {
                case 0:
                    t = I;
                    break;
                case 1:
                    t = S;
                    break;
                case 2:
                    t = B;
                    break;
                case 3:
                    if (opcode == 0x73) {
                        t = I;
                    } else {
                        t = U;
                    }
                    break;
                case 4:
                    t = U;
                    break;
                case 5:
                    t = J;
                    break;
            }
        }
    }

    static InstructionBase nop() {
        return InstructionBase(0x13);
    }

    bool is_nop() {
        return inst == 0x13;
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
        }
        return false;
    }

    void verify(const std::string &key) {
        if (!is_valid(key)) {
            throw InvalidAccess();
        }
    }

    void debug() {
        std::cout << "Instruction: " << inst << "\n";
        std::cout << "Type: " << t << "\n";
        std::cout << "Opcode: " << opcode << "\n";
        std::cout << "Rs1: " << rs1 << "\n";
        std::cout << "Rs2: " << rs2 << "\n";
        std::cout << "Rd: " << rd << "\n";
        std::cout << "Funct3: " << funct3 << "\n";
        std::cout << "Funct7: " << funct7 << "\n";
        std::cout << "Imm: " << imm.value() << "\n";
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
        imm = Immediate(expand_digit(get_digits(inst, 31, 20), 12));
    }
};

struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) : InstructionBase(inst) {
        imm = Immediate((expand_digit(get_digits(inst, 31, 25), 7) << 5) | get_digits(inst, 11, 7));
    }
};

struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) : InstructionBase(inst) {
        imm = Immediate((get_digits(inst, 31, 31) << 12) | (get_digits(inst, 7, 7) << 11) | (get_digits(inst, 12, 8) << 1) | (get_digits(inst, 6, 5) << 5));
    }
};

struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) : InstructionBase(inst) {
        imm = Immediate(get_digits(inst, 31, 12) << 12);
    }
};

struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) : InstructionBase(inst) {
        imm = Immediate((get_digits(inst, 31, 31) << 20) | (get_digits(inst, 19, 12) << 12) | (get_digits(inst, 20, 20) << 11) | (get_digits(inst, 30, 21) << 1));
    }
};

#endif //RISCV_SIMULATOR_INSTRUCTION_HPP