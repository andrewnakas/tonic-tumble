/* host shim for building the game's gzip code natively (tools/gzcheck) */
#pragma once
#include <string.h>
#include <stddef.h>
typedef unsigned char u8; typedef signed char s8; typedef unsigned short u16; typedef short s16;
typedef unsigned int u32; typedef int s32; typedef unsigned long long u64; typedef long long s64;
typedef float f32; typedef double f64; typedef u32 RomOffset; typedef u64 Gfx;
#define gsSPEndDisplayList() 0
