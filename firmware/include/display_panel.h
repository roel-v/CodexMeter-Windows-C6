#pragma once
#include <Arduino_GFX_Library.h>
#include "config.h"

#ifdef CODEXMETER_BOARD_C6
using CodexMeterPanel = Arduino_SH8601;
#else
using CodexMeterPanel = Arduino_CO5300;
#endif
