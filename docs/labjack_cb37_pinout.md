# LabJack T7 + CB37 Photometry Pinout

This pinout is the planned wiring map for the bilateral two-color photometry rig.

Use the CB37 screw terminals for the DB37 channels. Keep all external devices sharing a common ground with the LabJack. Do not connect external TTL pulses to `DAC0` or `DAC1`; those are LabJack outputs.

## Analog Outputs

| Purpose | LabJack channel | CB37 / DB37 pin | Wire to |
| --- | --- | --- | --- |
| 470 nm sine modulation | `DAC0` | pin `10` | 470 nm LED driver modulation input |
| 565 nm sine modulation | `DAC1` | pin `29` | 565 nm LED driver modulation input |
| Ground reference | `GND` | pins `1`, `9`, `20`, `28`, `30` | LED driver modulation ground |

The T7 DAC outputs are `0-5 V`. Use an offset sine wave such as `2.0 V offset, 1.0 V amplitude`, which produces a `1-3 V` command. Confirm the LED driver modulation input range before increasing offset or amplitude.

If recording the actual command waveforms, split or loop back:

| Loopback | Connect from | Connect to |
| --- | --- | --- |
| 470 nm command monitor | `DAC0` | `AIN2` |
| 565 nm command monitor | `DAC1` | `AIN3` |

## Analog Inputs

| Purpose | LabJack channel | CB37 / DB37 pin | Connect from |
| --- | --- | --- | --- |
| Left GCaMP8 detector amplifier | `AIN0` | pin `37` | amplifier voltage output |
| Right GCaMP8 detector amplifier | `AIN1` | pin `18` | amplifier voltage output |
| DAC0 monitor | `AIN2` | pin `36` | optional `DAC0` loopback |
| DAC1 monitor | `AIN3` | pin `17` | optional `DAC1` loopback |
| Left rdLight detector amplifier | `AIN4` | pin `35` | amplifier voltage output |
| Right rdLight detector amplifier | `AIN5` | pin `16` | amplifier voltage output |
| Lick analog board | `AIN6` | pin `34` | lick board analog output |
| Analog ground/reference | `GND` | pins `1`, `9`, `20`, `28`, `30` | amplifier/lick board ground |

Unused analog inputs can float and show meaningless voltages in Kipling. That is normal.

## Behavior TTL Inputs

| Purpose | LabJack channel | CB37 / DB37 pin | Connect from |
| --- | --- | --- | --- |
| Behavior sync pulse | `FIO0` | pin `6` | Teensy TTL output |
| Position bit 0 | `FIO1` | pin `25` | Teensy TTL output |
| Position bit 1 | `FIO2` | pin `5` | Teensy TTL output |
| Position bit 2 | `FIO3` | pin `24` | Teensy TTL output |
| Position strobe | `FIO4` | pin `4` | Teensy TTL output |
| Cue | `FIO5` | pin `23` | Teensy TTL output |
| Reward | `FIO6` | pin `3` | Teensy TTL output |
| Digital ground | `GND` | pins `1`, `9`, `20`, `28`, `30` | Teensy ground |

TTL should be `0-3.3 V` or `0-5 V`. The Teensy and LabJack must share ground.

## Spare CB37 Channels

| LabJack channel | CB37 / DB37 pin | Notes |
| --- | --- | --- |
| `AIN7` | pin `15` | spare analog input |
| `AIN8` | pin `33` | spare analog input |
| `AIN9` | pin `14` | spare analog input |
| `AIN10` | pin `32` | spare analog input |
| `AIN11` | pin `13` | spare analog input |
| `AIN12` | pin `31` | spare analog input |
| `AIN13` | pin `12` | spare analog input |
| `FIO7` | pin `22` | spare digital I/O |
| `MIO0` | pin `7` | spare digital I/O |
| `MIO1` | pin `8` | spare digital I/O |
| `MIO2` | pin `27` | spare digital I/O |

## Bench Checkout

Before connecting LED drivers:

1. Start with LED driver current limits set low.
2. In Kipling, set `DAC0` and `DAC1` manually to confirm the expected BNC/screw-terminal voltages.
3. Confirm `DAC0` and `DAC1` never exceed the LED driver modulation input range.
4. Confirm detector amplifier outputs on `AIN0` to `AIN3` stay within LabJack input range.
5. Confirm Teensy TTLs toggle the expected `FIO` channels.
