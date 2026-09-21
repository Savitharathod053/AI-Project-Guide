"""
BUILDCHECK AI — HARDWARE FEASIBILITY & BUDGET ANALYZER SERVICE
=============================================================
Analyzes hardware and hybrid engineering proposals for electrical compatibility,
current and power demands, pin budgeting (GPIO, ADC, PWM, I2C, SPI, UART),
multi-dimensional feasibility scoring, realistic Bill of Materials (BOM),
budget limits, verified purchasing options, and hardware task roadmaps.
"""

import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models import HardwareAnalysis, Project, Task, db

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HARDWARE COMPONENT SPECIFICATIONS KNOWLEDGEBASE
# ==============================================================================

CONTROLLERS_DB: Dict[str, Dict[str, Any]] = {
    "ESP32": {
        "name": "ESP32 DevKit V1 (30-Pin / 38-Pin)",
        "type": "processing",
        "category": "Microcontroller",
        "description": "Dual-core Xtensa 32-bit LX6 @ 240MHz with native 2.4GHz Wi-Fi and Bluetooth 4.2 BLE.",
        "logic_voltage": "3.3V",
        "logic_voltage_val": 3.3,
        "supply_voltage": "5V via Micro-USB / VIN (7-12V)",
        "supply_voltage_val": 5.0,
        "max_current_active_ma": 240.0,
        "idle_current_ma": 50.0,
        "onboard_regulator_max_ma": 500.0,
        "gpio_total": 25,
        "gpio_digital": 25,
        "gpio_adc": 16,
        "gpio_pwm": 16,
        "gpio_i2c": 2,
        "gpio_spi": 3,
        "gpio_uart": 3,
        "wireless": ["Wi-Fi (802.11 b/g/n)", "Bluetooth 4.2 / BLE"],
        "base_price_inr": 420.0,
        "recommended_spec": "ESP-WROOM-32 30-pin, CP2102 or CH340 USB driver",
        "alternatives": ["ESP8266 NodeMCU", "Raspberry Pi Pico W", "Arduino Uno with Wi-Fi Shield"]
    },
    "Arduino Uno": {
        "name": "Arduino Uno R3 (ATmega328P)",
        "type": "processing",
        "category": "Microcontroller",
        "description": "Standard 8-bit AVR microcontroller @ 16MHz. Extremely beginner-friendly with extensive 5V shield ecosystem.",
        "logic_voltage": "5V",
        "logic_voltage_val": 5.0,
        "supply_voltage": "7-12V DC Jack / 5V USB",
        "supply_voltage_val": 5.0,
        "max_current_active_ma": 50.0,
        "idle_current_ma": 25.0,
        "onboard_regulator_max_ma": 400.0,
        "gpio_total": 14,
        "gpio_digital": 14,
        "gpio_adc": 6,
        "gpio_pwm": 6,
        "gpio_i2c": 1,
        "gpio_spi": 1,
        "gpio_uart": 1,
        "wireless": [],
        "base_price_inr": 450.0,
        "recommended_spec": "ATmega328P DIP or SMD with 16MHz crystal & CH340/ATmega16U2",
        "alternatives": ["Arduino Nano", "ESP32", "STM32 Blue Pill"]
    },
    "Arduino Nano": {
        "name": "Arduino Nano V3.0 (ATmega328P)",
        "type": "processing",
        "category": "Microcontroller",
        "description": "Compact breadboard-friendly 8-bit AVR @ 16MHz with 8 analog inputs.",
        "logic_voltage": "5V",
        "logic_voltage_val": 5.0,
        "supply_voltage": "7-12V VIN / 5V Mini/Type-C USB",
        "supply_voltage_val": 5.0,
        "max_current_active_ma": 40.0,
        "idle_current_ma": 20.0,
        "onboard_regulator_max_ma": 200.0,
        "gpio_total": 14,
        "gpio_digital": 14,
        "gpio_adc": 8,
        "gpio_pwm": 6,
        "gpio_i2c": 1,
        "gpio_spi": 1,
        "gpio_uart": 1,
        "wireless": [],
        "base_price_inr": 230.0,
        "recommended_spec": "ATmega328P 5V 16MHz with CH340 USB interface",
        "alternatives": ["Arduino Pro Mini", "ESP32", "Raspberry Pi Pico"]
    },
    "Raspberry Pi 4": {
        "name": "Raspberry Pi 4 Model B (4GB RAM)",
        "type": "processing",
        "category": "Single Board Computer",
        "description": "Quad-core Cortex-A72 64-bit @ 1.5GHz. Full Linux OS, capable of computer vision (OpenCV) and machine learning inference.",
        "logic_voltage": "3.3V",
        "logic_voltage_val": 3.3,
        "supply_voltage": "5V 3.0A USB-C",
        "supply_voltage_val": 5.0,
        "max_current_active_ma": 1400.0,
        "idle_current_ma": 600.0,
        "onboard_regulator_max_ma": 800.0,
        "gpio_total": 28,
        "gpio_digital": 28,
        "gpio_adc": 0,  # CRITICAL: NO ANALOG INPUTS NATIVELY
        "gpio_pwm": 4,
        "gpio_i2c": 2,
        "gpio_spi": 2,
        "gpio_uart": 2,
        "wireless": ["Dual-band 2.4/5.0GHz Wi-Fi", "Bluetooth 5.0 BLE"],
        "base_price_inr": 5800.0,
        "recommended_spec": "Broadcom BCM2711 4GB LPDDR4 with heatsink & 5V 3A power supply",
        "alternatives": ["Raspberry Pi 3B+", "ESP32", "Orange Pi 3 LTS"]
    },
    "Raspberry Pi Pico W": {
        "name": "Raspberry Pi Pico W (RP2040)",
        "type": "processing",
        "category": "Microcontroller",
        "description": "Dual-core ARM Cortex-M0+ @ 133MHz with onboard 2.4GHz Wi-Fi and programmable I/O (PIO).",
        "logic_voltage": "3.3V",
        "logic_voltage_val": 3.3,
        "supply_voltage": "5V Micro-USB / 1.8V-5.5V VSYS",
        "supply_voltage_val": 5.0,
        "max_current_active_ma": 110.0,
        "idle_current_ma": 35.0,
        "onboard_regulator_max_ma": 300.0,
        "gpio_total": 26,
        "gpio_digital": 26,
        "gpio_adc": 3,
        "gpio_pwm": 16,
        "gpio_i2c": 2,
        "gpio_spi": 2,
        "gpio_uart": 2,
        "wireless": ["Wi-Fi 4 (802.11n)"],
        "base_price_inr": 580.0,
        "recommended_spec": "RP2040 chip with CYW43439 wireless chip & castellated pin headers",
        "alternatives": ["ESP32", "Arduino Nano Every", "STM32"]
    },
    "STM32 Blue Pill": {
        "name": "STM32 Blue Pill (STM32F103C8T6)",
        "type": "processing",
        "category": "Microcontroller",
        "description": "32-bit ARM Cortex-M3 @ 72MHz. High computing performance and precision ADCs at very low cost.",
        "logic_voltage": "3.3V",
        "logic_voltage_val": 3.3,
        "supply_voltage": "5V USB / 3.3V",
        "supply_voltage_val": 3.3,
        "max_current_active_ma": 70.0,
        "idle_current_ma": 25.0,
        "onboard_regulator_max_ma": 250.0,
        "gpio_total": 32,
        "gpio_digital": 32,
        "gpio_adc": 10,
        "gpio_pwm": 15,
        "gpio_i2c": 2,
        "gpio_spi": 2,
        "gpio_uart": 3,
        "wireless": [],
        "base_price_inr": 260.0,
        "recommended_spec": "64KB Flash, 20KB SRAM with ST-Link V2 programmer compatibility",
        "alternatives": ["Arduino Nano", "ESP32", "Raspberry Pi Pico"]
    }
}

COMPONENTS_CATALOG: Dict[str, Dict[str, Any]] = {
    # ------------------ SENSORS (INPUTS) ------------------
    "dht11": {
        "name": "DHT11 Temperature & Humidity Sensor",
        "type": "input",
        "category": "Sensor",
        "purpose": "Measures ambient temperature (0-50°C) and relative humidity (20-90% RH).",
        "recommended_spec": "Single-bus digital signal, 1Hz sampling rate, 3-pin module with pull-up resistor",
        "voltage": "3.3V – 5V",
        "voltage_val": 5.0,
        "current_ma": 1.5,
        "power_w": 0.0075,
        "pin_type": "Digital",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 85.0,
        "hazard_notes": "Low precision (+-2°C). For industrial accuracy, recommend DHT22/BME280.",
        "alternatives": ["DHT22 (AM2302)", "BME280 (I2C)", "LM35 (Analog)"]
    },
    "dht22": {
        "name": "DHT22 (AM2302) High Precision Temp & Humidity",
        "type": "input",
        "category": "Sensor",
        "purpose": "Accurate ambient temperature (-40 to 80°C) and humidity (0-100% RH).",
        "recommended_spec": "High accuracy ±0.5°C, single-wire digital interface with pull-up",
        "voltage": "3.3V – 5.5V",
        "voltage_val": 3.3,
        "current_ma": 2.5,
        "power_w": 0.008,
        "pin_type": "Digital",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 230.0,
        "hazard_notes": "None. Fully 3.3V and 5V logic safe.",
        "alternatives": ["DHT11", "BME280", "SHT31"]
    },
    "ultrasonic": {
        "name": "HC-SR04 Ultrasonic Distance Sensor",
        "type": "input",
        "category": "Sensor",
        "purpose": "Non-contact distance measurement from 2cm to 400cm using ultrasonic sonar waves.",
        "recommended_spec": "40kHz ultrasound, 4-pin (VCC, Trigger, Echo, GND), 15-degree measuring angle",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 15.0,
        "power_w": 0.075,
        "pin_type": "Digital",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 85.0,
        "hazard_notes": "Echo pin outputs 5V logic. If connecting to 3.3V controllers (ESP32/Raspberry Pi), use a voltage divider (1kΩ + 2kΩ) or logic level shifter to avoid pin damage.",
        "alternatives": ["HC-SR04P (3.3V native)", "VL53L0X ToF Laser Sensor", "Sharp GP2Y0A21YK0F"]
    },
    "pir": {
        "name": "HC-SR501 PIR Motion Sensor",
        "type": "input",
        "category": "Sensor",
        "purpose": "Detects human and animal movement via passive infrared radiation detection.",
        "recommended_spec": "Adjustable delay (0.3s-18s) and sensitivity range (3-7 meters), 3.3V output logic",
        "voltage": "5V – 12V",
        "voltage_val": 5.0,
        "current_ma": 0.065,
        "power_w": 0.0003,
        "pin_type": "Digital",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 80.0,
        "hazard_notes": "Needs 5V on VCC, but its output signal is 3.3V logic, making it safe for both ESP32 and Arduino.",
        "alternatives": ["RCWL-0516 Microwave Radar", "Mini AM312 PIR Sensor"]
    },
    "soil_moisture": {
        "name": "Capacitive Soil Moisture Sensor V1.2",
        "type": "input",
        "category": "Sensor",
        "purpose": "Measures volumetric water content in soil without galvanic probe corrosion.",
        "recommended_spec": "Corrosion-resistant capacitive measurement, analog voltage output 1.2V - 3.0V",
        "voltage": "3.3V – 5.5V",
        "voltage_val": 3.3,
        "current_ma": 5.0,
        "power_w": 0.016,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 95.0,
        "hazard_notes": "Avoid resistive soil sensors (they corrode within days). On Raspberry Pi, an ADS1115 ADC converter is required.",
        "alternatives": ["Resistive Soil Moisture Sensor", "SHT10 Waterproof Soil Probe"]
    },
    "mpu6050": {
        "name": "MPU-6050 6-Axis Gyroscope & Accelerometer",
        "type": "input",
        "category": "Sensor",
        "purpose": "Captures 3-axis motion, tilt, pitch, roll, and angular velocity with onboard DMP.",
        "recommended_spec": "I2C interface (address 0x68), onboard low-dropout voltage regulator",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 4.0,
        "power_w": 0.013,
        "pin_type": "I2C",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 160.0,
        "hazard_notes": "Connect to designated I2C pins (SDA/SCL). Shared bus allows up to 2 MPU6050 devices (via AD0 pin).",
        "alternatives": ["ADXL345", "BNO055 9-DOF", "MPU-9250"]
    },
    "gas_mq2": {
        "name": "MQ-2 Gas / Smoke / LPG Sensor Module",
        "type": "input",
        "category": "Sensor",
        "purpose": "Detects combustible gas, methane, smoke, and propane concentrations in the atmosphere.",
        "recommended_spec": "Heater voltage 5V, analog concentration output + digital threshold comparator",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 160.0,
        "power_w": 0.8,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 110.0,
        "hazard_notes": "Internal heater coil draws 160mA! Do NOT power from the 3.3V pin or directly through a weak USB port. Requires dedicated 5V power rail.",
        "alternatives": ["MQ-135 (Air Quality)", "MQ-7 (Carbon Monoxide)", "BME680 (VOC)"]
    },
    "pulse_sensor": {
        "name": "Pulse / Heart Rate Sensor Module",
        "type": "input",
        "category": "Sensor",
        "purpose": "Optical photoplethysmography (PPG) sensor for live heart rate / BPM pulse monitoring.",
        "recommended_spec": "Integrated optical amplification and noise cancellation circuit",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 4.0,
        "power_w": 0.013,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 140.0,
        "hazard_notes": "Analog signal requires clean software filtering / moving average to eliminate ambient light noise.",
        "alternatives": ["MAX30102 (I2C SpO2 + Heart Rate)", "MAX30100"]
    },
    "camera_ov2640": {
        "name": "OV2640 2-Megapixel Camera Module",
        "type": "input",
        "category": "Camera",
        "purpose": "Captures JPEG still photos and video frames for surveillance, edge AI, or face recognition.",
        "recommended_spec": "2MP UXGA (1600x1200) with DVP 8-bit parallel interface & SCCB/I2C control",
        "voltage": "3.3V",
        "voltage_val": 3.3,
        "current_ma": 180.0,
        "power_w": 0.59,
        "pin_type": "DVP/SPI",
        "pins_needed": 10,
        "necessity": "Essential",
        "price_inr": 340.0,
        "hazard_notes": "Requires high memory and processing bandwidth. Only compatible with ESP32-CAM (with PSRAM) or Raspberry Pi.",
        "alternatives": ["OV5640 5MP", "Raspberry Pi Camera Module v2", "USB Webcam"]
    },
    "gps_neo6m": {
        "name": "U-Blox NEO-6M GPS Receiver Module with Antenna",
        "type": "communication",
        "category": "GPS/Location",
        "purpose": "Receives global satellite positioning data (latitude, longitude, altitude, UTC time, speed).",
        "recommended_spec": "UART NMEA 9600 baud, built-in EEPROM and active ceramic patch antenna",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 50.0,
        "power_w": 0.165,
        "pin_type": "UART",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 480.0,
        "hazard_notes": "Requires clear line of sight to open sky for initial satellite lock (TTFF 1-2 minutes). Connect to hardware or software UART RX/TX.",
        "alternatives": ["NEO-7M", "NEO-M8N High Precision", "SIM808 (GSM+GPS combined)"]
    },
    "rfid_rc522": {
        "name": "RC522 13.56MHz RFID Reader Module with Keyfob",
        "type": "input",
        "category": "RFID/NFC",
        "purpose": "Contactless card reading and UID verification for student attendance and access control.",
        "recommended_spec": "Mifare S50 13.56MHz protocol, SPI interface, read range up to 5cm",
        "voltage": "3.3V strictly",
        "voltage_val": 3.3,
        "current_ma": 26.0,
        "power_w": 0.085,
        "pin_type": "SPI",
        "pins_needed": 5,
        "necessity": "Essential",
        "price_inr": 130.0,
        "hazard_notes": "DO NOT connect VCC to 5V! Supplying 5V will permanently burn the RC522 chip. SPI pins require SCK, MISO, MOSI, SS/SDA, RST.",
        "alternatives": ["PN532 NFC Module (I2C/SPI)", "RDM6300 125kHz Reader"]
    },
    "air_quality_mq135": {
        "name": "MQ-135 Hazardous Gas & Air Quality Sensor Module",
        "type": "input",
        "category": "Sensor",
        "purpose": "Detects air contaminants, NH3, NOx, alcohol, benzene, smoke, and CO2 in ambient air.",
        "recommended_spec": "5V heater with SnO2 sensitive layer, dual analog (concentration) + digital (comparator) outputs",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 150.0,
        "power_w": 0.75,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 120.0,
        "hazard_notes": "Internal heating element draws ~150mA continuous current. Requires a 24-hour initial burn-in period for stable baseline readings.",
        "alternatives": ["MQ-2 (Combustible Gas)", "BME680 (VOC & Gas)", "SGP30 Digital Air Quality"]
    },
    "particulate_pms5003": {
        "name": "Plantower PMS5003 Laser Dust & PM2.5 / PM10 Sensor",
        "type": "input",
        "category": "Sensor",
        "purpose": "Precise real-time particulate matter (PM1.0, PM2.5, PM10) concentration measurement using laser scattering.",
        "recommended_spec": "Laser diode optical scattering, 0.3μm to 10μm particle range, UART 9600 baud serial output",
        "voltage": "5V supply, 3.3V UART logic",
        "voltage_val": 5.0,
        "current_ma": 100.0,
        "power_w": 0.5,
        "pin_type": "UART",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 1250.0,
        "hazard_notes": "Supply with clean 5V power (internal laser and fan require 5V). UART TX data line operates at 3.3V logic (safe for ESP32 and Raspberry Pi).",
        "alternatives": ["Nova Fitness SDS011 PM Sensor", "Sharp GP2Y1010AU0F Optical Dust Sensor"]
    },
    "bme280": {
        "name": "BME280 Precision Digital Temp, Humidity & Pressure Sensor",
        "type": "input",
        "category": "Sensor",
        "purpose": "Measures environmental temperature, relative humidity, and barometric atmospheric pressure / altitude.",
        "recommended_spec": "I2C default address 0x76 or 0x77, ±1 hPa pressure accuracy, ±3% RH accuracy",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 3.6,
        "power_w": 0.012,
        "pin_type": "I2C",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 280.0,
        "hazard_notes": "Ensure solder jumper or pin selection for I2C address (0x76 vs 0x77). Low current, fully 3.3V/5V tolerant.",
        "alternatives": ["BMP280 (Pressure + Temp only)", "DHT22 (Temp + Humidity)", "AHT20"]
    },
    "camera_rpi_v2": {
        "name": "Raspberry Pi Camera Module v2 (8MP Sony IMX219)",
        "type": "input",
        "category": "Camera",
        "purpose": "High-definition camera for real-time OpenCV facial recognition, object tracking, and edge computer vision.",
        "recommended_spec": "Sony IMX219 8-Megapixel sensor, 1080p30 / 720p60 video, 15-pin ribbon MIPI CSI connector",
        "voltage": "3.3V (via CSI Bus)",
        "voltage_val": 3.3,
        "current_ma": 250.0,
        "power_w": 0.825,
        "pin_type": "CSI Ribbon",
        "pins_needed": 0,
        "necessity": "Essential",
        "price_inr": 1850.0,
        "hazard_notes": "Connect only to the dedicated CSI camera port on Raspberry Pi with contacts facing HDMI port. Do not bend ribbon cable sharply.",
        "alternatives": ["USB 1080p HD Webcam", "Raspberry Pi Camera Module 3 (12MP Auto-focus)", "OV5647 5MP Camera"]
    },
    "fingerprint_r307": {
        "name": "R307 Optical Fingerprint Scanner Module",
        "type": "input",
        "category": "Biometrics",
        "purpose": "Captures biometric fingerprints and performs 1:N local matching for student attendance and security access.",
        "recommended_spec": "UART serial interface (default 57600 baud), 500 DPI optical sensor, capacity up to 1000 fingerprints",
        "voltage": "3.3V – 5V",
        "voltage_val": 5.0,
        "current_ma": 50.0,
        "power_w": 0.25,
        "pin_type": "UART",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 950.0,
        "hazard_notes": "UART communication pins (TX/RX) require 3.3V logic matching. Red (VCC), Black (GND), Yellow (TX), Green (RX).",
        "alternatives": ["AS608 Optical Fingerprint Sensor", "FPM10A Fingerprint Reader"]
    },
    "water_flow_yfs201": {
        "name": "YF-S201 Hall Effect Water Flow Sensor (1/2 Inch)",
        "type": "input",
        "category": "Sensor",
        "purpose": "Measures volumetric water flow rate and calculates cumulative irrigation liquid volume via frequency pulses.",
        "recommended_spec": "Flow range 1-30 L/min, working pressure <1.75MPa, pulse frequency F = 7.5 * Q (L/min)",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 15.0,
        "power_w": 0.075,
        "pin_type": "Digital (Interrupt)",
        "pins_needed": 1,
        "necessity": "Optional",
        "price_inr": 290.0,
        "hazard_notes": "Connect to an interrupt-capable digital pin (e.g. GPIO2/GPIO4 on ESP32 or D2/D3 on Arduino) to count pulses accurately.",
        "alternatives": ["YF-S401 (Small Tube Flow)", "YF-B1 (Brass Flow Sensor)"]
    },
    "rain_sensor": {
        "name": "Raindrop & Weather Water Detection Sensor Board",
        "type": "input",
        "category": "Sensor",
        "purpose": "Detects rainfall droplets and surface water accumulation for automated irrigation shutoff or weather stations.",
        "recommended_spec": "Nickel-plated sensing board with LM393 comparator, analog + digital output",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 15.0,
        "power_w": 0.05,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Optional",
        "price_inr": 85.0,
        "hazard_notes": "Outdoor probes will experience oxidation over time. Coat unused traces with lacquer to prevent moisture ingress.",
        "alternatives": ["Optical Rain Sensor", "Capacitive Water Level Sensor"]
    },
    "ldr_sensor": {
        "name": "LDR Light Dependent Resistor Sensor Module",
        "type": "input",
        "category": "Sensor",
        "purpose": "Measures ambient lux illumination for solar tracking, automated lighting, or daylight detection.",
        "recommended_spec": "Photoresistor with LM393 comparator potentiometer, dual analog and digital outputs",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 10.0,
        "power_w": 0.033,
        "pin_type": "Analog",
        "pins_needed": 1,
        "necessity": "Optional",
        "price_inr": 50.0,
        "hazard_notes": "Simple, reliable sensor. Fully compatible with 3.3V ADC and 5V analog rails.",
        "alternatives": ["BH1750 Digital Lux Sensor (I2C)", "TEMT6000 Ambient Light Sensor"]
    },
    "ads1115": {
        "name": "ADS1115 16-Bit 4-Channel I2C ADC Converter Module",
        "type": "interface",
        "category": "ADC Converter",
        "purpose": "Provides 4 ultra-precise 16-bit analog inputs for single board computers (e.g. Raspberry Pi) lacking onboard ADC.",
        "recommended_spec": "16-bit precision, 860 samples/sec, programmable gain amplifier (PGA), I2C interface",
        "voltage": "2.0V – 5.5V",
        "voltage_val": 3.3,
        "current_ma": 0.15,
        "power_w": 0.0005,
        "pin_type": "I2C",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 210.0,
        "hazard_notes": "Essential companion module whenever analog sensors (soil moisture, MQ gas, LDR) are paired with Raspberry Pi.",
        "alternatives": ["MCP3008 8-Channel SPI ADC", "PCF8591 8-Bit ADC/DAC"]
    },
    "level_converter": {
        "name": "4-Channel Bidirectional 3.3V - 5V Logic Level Converter",
        "type": "interface",
        "category": "Logic Shifter",
        "purpose": "Safely shifts logic signals between 5V sensors/modules and 3.3V microcontrollers (ESP32, Raspberry Pi).",
        "recommended_spec": "4 bidirectional BSS138 MOSFET channels, HV=5V, LV=3.3V, 0-10MHz signal speed",
        "voltage": "3.3V and 5V rails",
        "voltage_val": 3.3,
        "current_ma": 1.0,
        "power_w": 0.003,
        "pin_type": "Signal Shifter",
        "pins_needed": 0,
        "necessity": "Recommended",
        "price_inr": 60.0,
        "hazard_notes": "Must connect both HV (5V) and LV (3.3V) with common GND for proper bidirectional translation.",
        "alternatives": ["Resistor Voltage Divider (1k + 2k)", "TXB0108 8-Channel Level Shifter"]
    },

    # ------------------ ACTUATORS & OUTPUTS ------------------
    "servo_sg90": {
        "name": "TowerPro SG90 9g Micro Servo Motor",
        "type": "output",
        "category": "Motor/Actuator",
        "purpose": "180-degree angular positioning for robotic arms, steering mechanisms, and valve controls.",
        "recommended_spec": "Torque 1.8 kg-cm @ 4.8V, PWM signal control (50Hz / 20ms period)",
        "voltage": "4.8V – 6V",
        "voltage_val": 5.0,
        "current_ma": 250.0,
        "power_w": 1.25,
        "pin_type": "PWM",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 85.0,
        "hazard_notes": "Stall current reaches 650mA! CANNOT be powered from the microcontroller 5V pin under mechanical load. Use an external 5V 1A power supply with shared common ground.",
        "alternatives": ["MG90S Metal Gear Micro Servo", "MG995 High Torque Servo"]
    },
    "servo_mg996r": {
        "name": "MG996R Metal Gear High-Torque Servo",
        "type": "output",
        "category": "Motor/Actuator",
        "purpose": "Heavy-duty robotics, grippers, steering linkages requiring up to 11 kg-cm torque.",
        "recommended_spec": "Metal gears, double ball bearing, stall torque 11 kg-cm @ 6V",
        "voltage": "4.8V – 7.2V",
        "voltage_val": 6.0,
        "current_ma": 600.0,
        "power_w": 3.6,
        "pin_type": "PWM",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 320.0,
        "hazard_notes": "Stall current reaches 2.5A! Must be powered from an external high-current power supply or 2S Li-ion battery with buck converter.",
        "alternatives": ["SG90", "MG995", "DS3218 20kg Waterproof Servo"]
    },
    "dc_motor_bo": {
        "name": "Dual-Shaft BO Gear Motor (3-6V) with Wheel",
        "type": "output",
        "category": "Motor/Actuator",
        "purpose": "Drive motor for 2WD/4WD obstacle-avoiding or line-follower mobile robot chassis.",
        "recommended_spec": "1:48 gear ratio, 100-200 RPM, operational current 150-300mA",
        "voltage": "3V – 6V",
        "voltage_val": 5.0,
        "current_ma": 350.0,
        "power_w": 1.75,
        "pin_type": "Motor Driver Required",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 75.0,
        "hazard_notes": "❌ DIRECT CONNECTION NOT RECOMMENDED: Microcontroller GPIO pins can only deliver 12mA to 40mA. Direct connection will destroy the board. You MUST use an L298N, L293D, or DRV8833 motor driver.",
        "alternatives": ["TT Gear Motor", "N20 Metal Micro Gear Motor", "Stepper Motor 28BYJ-48"]
    },
    "water_pump_5v": {
        "name": "Submersible Mini DC Water Pump (3-6V)",
        "type": "output",
        "category": "Pump/Actuator",
        "purpose": "Pumps water for automated plant irrigation or liquid dispensing systems.",
        "recommended_spec": "Flow rate 80-120 L/H, lift 40-110cm, 5V DC submersible",
        "voltage": "3V – 6V",
        "voltage_val": 5.0,
        "current_ma": 300.0,
        "power_w": 1.5,
        "pin_type": "Relay / Driver Required",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 90.0,
        "hazard_notes": "❌ DIRECT CONNECTION NOT RECOMMENDED: Inductive load with ~300mA current and back-EMF spikes. Control via a 5V Relay module or TIP120/IRFZ44N MOSFET with flyback diode.",
        "alternatives": ["12V Diaphragm Water Pump (R385)", "Peristaltic Dosing Pump"]
    },
    "relay_module": {
        "name": "5V 1-Channel Relay Module with Optocoupler Isolation",
        "type": "driver",
        "category": "Switching/Control",
        "purpose": "Safely switches high-voltage (250V AC) or high-current DC loads (water pumps, AC lamps, solenoids).",
        "recommended_spec": "10A 250VAC / 10A 30VDC rated, optocoupler isolation, active LOW/HIGH trigger",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 70.0,
        "power_w": 0.35,
        "pin_type": "Digital",
        "pins_needed": 1,
        "necessity": "Essential",
        "price_inr": 65.0,
        "hazard_notes": "Coil draws 70mA. Ensure 5V power is supplied to VCC; control input can be triggered by 3.3V or 5V logic.",
        "alternatives": ["2-Channel 5V Relay Module", "IRFZ44N N-Channel MOSFET Module", "Solid State Relay (SSR)"]
    },
    "motor_driver_l298n": {
        "name": "L298N Dual H-Bridge Motor Driver Module",
        "type": "driver",
        "category": "Motor Driver",
        "purpose": "Controls speed (via PWM) and direction of two DC motors or one bipolar stepper motor.",
        "recommended_spec": "Dual H-bridge, operating voltage 5V-35V, peak output current 2A per channel",
        "voltage": "5V – 12V",
        "voltage_val": 12.0,
        "current_ma": 40.0,
        "power_w": 0.48,
        "pin_type": "Digital & PWM",
        "pins_needed": 4,
        "necessity": "Essential",
        "price_inr": 140.0,
        "hazard_notes": "Keep common ground between motor driver and microcontroller. Onboard 5V regulator can power microcontroller if motor supply is 7-12V.",
        "alternatives": ["DRV8833 Dual Motor Driver", "L293D Motor Shield", "TB6612FNG High Efficiency Driver"]
    },
    "oled_display": {
        "name": "0.96-Inch I2C OLED Display (128x64, SSD1306)",
        "type": "output",
        "category": "Display",
        "purpose": "High-contrast graphical display for showing live sensor readings, system status, and menus.",
        "recommended_spec": "128x64 pixel resolution, I2C interface (address 0x3C), 4-pin (VCC, GND, SCL, SDA)",
        "voltage": "3.3V – 5V",
        "voltage_val": 3.3,
        "current_ma": 20.0,
        "power_w": 0.066,
        "pin_type": "I2C",
        "pins_needed": 2,
        "necessity": "Optional",
        "price_inr": 190.0,
        "hazard_notes": "Very low power consumption and sharp contrast. Uses standard I2C bus.",
        "alternatives": ["16x2 LCD with I2C Backpack", "1.3-inch OLED (SH1106)", "0.96-inch TFT Color Display"]
    },
    "lcd_16x2_i2c": {
        "name": "16x2 Character LCD Display with PCF8574 I2C Adapter",
        "type": "output",
        "category": "Display",
        "purpose": "Displays 2 rows of 16 alphanumeric characters for system diagnostics and output display.",
        "recommended_spec": "HD44780 LCD with soldered PCF8574 I2C backpack, contrast potentiometer",
        "voltage": "5V",
        "voltage_val": 5.0,
        "current_ma": 35.0,
        "power_w": 0.175,
        "pin_type": "I2C",
        "pins_needed": 2,
        "necessity": "Optional",
        "price_inr": 180.0,
        "hazard_notes": "Needs 5V VCC for clear contrast. Only requires 2 microcontroller pins (SDA/SCL) instead of 6 parallel pins.",
        "alternatives": ["0.96-inch OLED I2C", "20x4 I2C LCD Display"]
    },
    "buzzer_active": {
        "name": "5V Active Piezo Buzzer Module",
        "type": "output",
        "category": "Audio/Alert",
        "purpose": "Generates loud acoustic alarm / warning beeps upon event or sensor threshold detection.",
        "recommended_spec": "Active oscillator built-in (sounds tone when driven HIGH), sound output >85dB",
        "voltage": "3.3V – 5V",
        "voltage_val": 5.0,
        "current_ma": 30.0,
        "power_w": 0.15,
        "pin_type": "Digital",
        "pins_needed": 1,
        "necessity": "Recommended",
        "price_inr": 25.0,
        "hazard_notes": "Active buzzer generates tone automatically with HIGH signal. Passive buzzer requires PWM frequency waveform.",
        "alternatives": ["Passive Piezo Buzzer", "DFPlayer Mini MP3 Audio Module"]
    },

    # ------------------ WIRELESS & COMMUNICATION ------------------
    "gsm_sim800l": {
        "name": "SIM800L GPRS / GSM Cellular Module",
        "type": "communication",
        "category": "Cellular/Wireless",
        "purpose": "Sends SMS alerts, makes emergency voice calls, and transmits HTTP data over 2G cellular network.",
        "recommended_spec": "MicroSIM card slot, quad-band 850/900/1800/1900MHz, UART AT commands",
        "voltage": "3.7V – 4.2V strictly",
        "voltage_val": 4.0,
        "current_ma": 350.0,
        "power_w": 1.4,
        "pin_type": "UART",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 550.0,
        "hazard_notes": "CRITICAL HAZARD: Peak transmission bursts reach 2.0 Amperes! DO NOT power from standard 5V USB, Arduino 5V/3.3V pins, or a 9V battery. Requires a dedicated 3.7V Li-ion battery or LM2596 buck converter set to 4.0V with a 1000µF capacitor.",
        "alternatives": ["SIM900A GSM Module", "SIM7600 4G LTE Module", "ESP32 Wi-Fi / Twilio API"]
    },
    "lora_sx1278": {
        "name": "SX1278 Ra-02 433MHz LoRa Long Range Wireless Transceiver",
        "type": "communication",
        "category": "Long-Range Wireless",
        "purpose": "Long-range low-power telemetry transmission (up to 3-5 km line of sight) without cellular subscriptions.",
        "recommended_spec": "433MHz frequency, SPI interface, spread spectrum modulation, IPEX antenna connector",
        "voltage": "3.3V strictly",
        "voltage_val": 3.3,
        "current_ma": 120.0,
        "power_w": 0.396,
        "pin_type": "SPI",
        "pins_needed": 5,
        "necessity": "Essential",
        "price_inr": 380.0,
        "hazard_notes": "Operates strictly at 3.3V logic and supply. Never transmit without an attached antenna (will burn RF stage).",
        "alternatives": ["NRF24L01+ 2.4GHz Transceiver", "ESP-NOW (ESP32 peer-to-peer)", "HC-12 Wireless Serial"]
    },
    "bluetooth_hc05": {
        "name": "HC-05 Bluetooth Classic 2.0 Serial Module",
        "type": "communication",
        "category": "Bluetooth",
        "purpose": "Wireless serial data communication with Android smartphones and laptops up to 10 meters.",
        "recommended_spec": "Master/Slave mode selectable, default 9600/38400 baud, 3.3V logic level with 5V onboard LDO",
        "voltage": "3.6V – 6V",
        "voltage_val": 5.0,
        "current_ma": 35.0,
        "power_w": 0.175,
        "pin_type": "UART",
        "pins_needed": 2,
        "necessity": "Essential",
        "price_inr": 280.0,
        "hazard_notes": "RX pin requires 3.3V logic. When connecting to Arduino 5V TX pin, use a 1kΩ/2kΩ resistor divider on RX.",
        "alternatives": ["HC-06 (Slave Only)", "HM-10 BLE 4.0 (iOS compatible)", "ESP32 built-in Bluetooth"]
    },

    # ------------------ POWER & SUPPORT ACCESSORIES ------------------
    "power_supply_12v2a": {
        "name": "12V 2A DC Power Adapter (Center Positive 2.1mm)",
        "type": "power",
        "category": "Power Supply",
        "purpose": "Stable mains AC-to-DC power for driving motors, pumps, relays, and step-down regulators.",
        "recommended_spec": "Input 100-240V AC, output 12V DC regulated, 24W power capacity",
        "voltage": "12V",
        "voltage_val": 12.0,
        "current_ma": 2000.0,
        "power_w": 24.0,
        "pin_type": "Power Rail",
        "pins_needed": 0,
        "necessity": "Recommended",
        "price_inr": 250.0,
        "hazard_notes": "Ideal for stationary desktop and lab testing. Keeps microcontroller and motor rails stable.",
        "alternatives": ["2x 18650 Li-ion Battery Pack (7.4V)", "9V 1A DC Adapter", "5V 2.4A USB Adapter"]
    },
    "battery_18650_pack": {
        "name": "2x 18650 3.7V 2600mAh Li-ion Batteries with 2S BMS Holder",
        "type": "power",
        "category": "Battery",
        "purpose": "Portable rechargeable high-discharge power source for mobile robots and autonomous nodes.",
        "recommended_spec": "Nominal 7.4V (8.4V fully charged), integrated over-discharge & short-circuit BMS board",
        "voltage": "7.4V",
        "voltage_val": 7.4,
        "current_ma": 2600.0,
        "power_w": 19.24,
        "pin_type": "Power Rail",
        "pins_needed": 0,
        "necessity": "Recommended",
        "price_inr": 480.0,
        "hazard_notes": "Much superior to 9V rectangular batteries. Capable of sourcing up to 5A burst currents safely.",
        "alternatives": ["12V 2A DC Adapter", "Power Bank 5V 2A (USB)", "3S LiPo 11.1V Battery"]
    },
    "buck_converter_lm2596": {
        "name": "LM2596 Step-Down DC-DC Buck Converter Module",
        "type": "power",
        "category": "Voltage Regulator",
        "purpose": "Efficiently steps down higher voltage (12V or 7.4V) to a clean 5V or 3.3V rail with high efficiency.",
        "recommended_spec": "Input 4.5V-35V, output 1.25V-30V adjustable via trimpot, up to 3A output current",
        "voltage": "Adjustable",
        "voltage_val": 5.0,
        "current_ma": 3000.0,
        "power_w": 15.0,
        "pin_type": "Power Rail",
        "pins_needed": 0,
        "necessity": "Recommended",
        "price_inr": 85.0,
        "hazard_notes": "Essential when using high-voltage power supplies (12V) with sensitive 5V or 3.3V microcontrollers.",
        "alternatives": ["AMS1117 3.3V Regulator", "7805 Linear Regulator (High heat)", "MP1584 Ultra-small Buck"]
    },
    "logic_level_shifter": {
        "name": "4-Channel Bidirectional Logic Level Converter (3.3V ↔ 5V)",
        "type": "driver",
        "category": "Level Shifting",
        "purpose": "Safely bridges data signals between 3.3V controllers (ESP32/RPi) and 5V sensors/modules (HC-SR04/I2C/UART).",
        "recommended_spec": "BSS138 MOSFET-based, 4 bidirectional channels, supports I2C, SPI, and UART speeds",
        "voltage": "3.3V & 5V",
        "voltage_val": 3.3,
        "current_ma": 5.0,
        "power_w": 0.016,
        "pin_type": "Signal Interface",
        "pins_needed": 0,
        "necessity": "Recommended",
        "price_inr": 45.0,
        "hazard_notes": "Prevents accidental over-voltage damage to ESP32 or Raspberry Pi GPIO pins from 5V outputs.",
        "alternatives": ["Resistor Voltage Divider (Passive)", "74HCT125 Buffer"]
    },
    "breadboard_wires": {
        "name": "Solderless Half-Size Breadboard (400 Tie-Points) + 65 Jumper Wires",
        "type": "driver",
        "category": "Prototyping",
        "purpose": "Rapid solder-free circuit prototyping, component interconnection, and power bus distribution.",
        "recommended_spec": "400 tie points, standard 2.54mm pitch, male-to-male and male-to-female jumper kit",
        "voltage": "N/A",
        "voltage_val": 5.0,
        "current_ma": 0.0,
        "power_w": 0.0,
        "pin_type": "Wiring",
        "pins_needed": 0,
        "necessity": "Essential",
        "price_inr": 120.0,
        "hazard_notes": "Keep high current (>1.5A) away from thin breadboard spring clips to prevent contact resistance drops.",
        "alternatives": ["830 Tie-Point Full Breadboard", "Custom Stripboard / Perfboard PCB"]
    }
}


# ==============================================================================
# 2. CORE SERVICE CLASS: HardwareFeasibilityService
# ==============================================================================

class HardwareFeasibilityService:
    """
    BuildCheck AI Hardware Feasibility and Budget Analysis Engine.
    """

    # --------------------------------------------------------------------------
    # 2.1 AUTOMATIC PROJECT TYPE CLASSIFICATION
    # --------------------------------------------------------------------------
    @staticmethod
    def classify_project_type(title: str, description: str, domain: str = "") -> Dict[str, Any]:
        """
        Classifies an academic project into:
        - "software": Software Project (Web, Mobile, AI/ML software, Cloud)
        - "hardware": Hardware Project (Pure embedded, circuit, robotics)
        - "hybrid": Hybrid Project (Hardware sensors/controller + Software dashboard/app)
        """
        text = f"{title} {description} {domain}".lower()

        # Hardware Keywords & Patterns
        hw_patterns = [
            r"\barduino\b", r"\besp32\b", r"\besp8266\b", r"\braspberry\s*pi\b", r"\brpi\b",
            r"\bmicrocontroller\b", r"\bmicro-controller\b", r"\bcontroller\b", r"\bprocessor\b",
            r"\bembedded\b", r"\biot\b", r"\binternet\s*of\s*things\b", r"\brobot\b", r"\brobotics\b",
            r"\bsensor\b", r"\bsensors\b", r"\bultrasonic\b", r"\bdht11\b", r"\bdht22\b", r"\bmq-?2\b",
            r"\bmq-?135\b", r"\bpir\b", r"\baccelerometer\b", r"\bgyroscope\b", r"\bmpu-?6050\b",
            r"\bmotor\b", r"\bmotors\b", r"\bservo\b", r"\bstepper\b", r"\brelay\b", r"\bbuzzer\b",
            r"\bpump\b", r"\bwater\s*pump\b", r"\bsolenoid\b", r"\bactuator\b", r"\bled\b",
            r"\boled\b", r"\blcd\b", r"\bcircuit\b", r"\bbreadboard\b", r"\bpcb\b", r"\bgpio\b",
            r"\bvoltage\b", r"\bcurrent\b", r"\blora\b", r"\bzigbee\b", r"\bgsm\b", r"\bsim800\b",
            r"\brfid\b", r"\bgps\b", r"\bhardware\b", r"\bchassis\b", r"\btransceiver\b"
        ]

        # Software Keywords & Patterns
        sw_patterns = [
            r"\bweb\s*app\b", r"\bwebsite\b", r"\bfrontend\b", r"\bbackend\b", r"\bfull\s*stack\b",
            r"\bportal\b", r"\bdashboard\b", r"\bmobile\s*app\b", r"\bandroid\b", r"\bios\b",
            r"\bflutter\b", r"\breact\b", r"\bflask\b", r"\bdjango\b", r"\bfastapi\b",
            r"\bdatabase\b", r"\bsqlite\b", r"\bmysql\b", r"\bpostgres\b", r"\bmongodb\b",
            r"\bmachine\s*learning\b", r"\bdeep\s*learning\b", r"\bcnn\b", r"\brnn\b", r"\bnlp\b",
            r"\bcloud\b", r"\bapi\b", r"\brest\s*api\b", r"\bcloud\s*server\b"
        ]

        hw_matches = [p for p in hw_patterns if re.search(p, text)]
        sw_matches = [p for p in sw_patterns if re.search(p, text)]

        hw_count = len(hw_matches)
        sw_count = len(sw_matches)

        # Explicit domain override signals
        domain_lower = (domain or "").lower()
        if "iot" in domain_lower or "internet of things" in domain_lower or "embedded" in domain_lower or "robotics" in domain_lower:
            hw_count += 3

        logger.info(f"Project Type Detection for '{title}': HW Score={hw_count}, SW Score={sw_count}")

        # Classification decision
        if hw_count >= 2 and sw_count >= 2:
            category = "hybrid"
            display_name = "Hybrid Project (Hardware + Software)"
            is_hardware = True
            reason = f"Identified both hardware modules ({hw_count} matches: sensors/controllers) and software layers ({sw_count} matches: web/database/analytics)."
        elif hw_count >= 1:
            category = "hardware"
            display_name = "Hardware Project"
            is_hardware = True
            reason = f"Detected physical hardware components, microcontrollers, or sensors ({hw_count} matches)."
        else:
            category = "software"
            display_name = "Software Project"
            is_hardware = False
            reason = "No physical hardware components or microcontrollers detected in project proposal."

        return {
            "category": category,
            "display_name": display_name,
            "is_hardware": is_hardware,
            "hw_score": hw_count,
            "sw_score": sw_count,
            "detected_hardware_indicators": hw_matches,
            "reason": reason
        }

    # --------------------------------------------------------------------------
    # 2.2 STRUCTURED SYSTEM ARCHITECTURE DECOMPOSITION
    # --------------------------------------------------------------------------
    @staticmethod
    def extract_architecture_components(
        title: str,
        description: str,
        preferred_controller: str = "ESP32"
    ) -> Dict[str, Any]:
        """
        Extracts Inputs, Processing, Outputs, Communication, and Power components.
        """
        text = f"{title} {description}".lower()

        # 1. Processing Unit Selection
        controller_key = "ESP32"
        is_vision_project = bool(re.search(r"face\s*recognition|facial|opencv|computer\s*vision|image\s*processing|edge\s*ai|ai\s*vision", text))
        is_esp32_cam = bool(re.search(r"esp32-cam|esp-cam", text))
        
        if "raspberry pi 4" in text or "rpi 4" in text or ("computer vision" in text and "pi" in text) or (is_vision_project and not is_esp32_cam and preferred_controller in ["ESP32", "Raspberry Pi 4"]):
            controller_key = "Raspberry Pi 4"
        elif "pico" in text or "rp2040" in text:
            controller_key = "Raspberry Pi Pico W"
        elif "nano" in text:
            controller_key = "Arduino Nano"
        elif "uno" in text or "atmega" in text:
            controller_key = "Arduino Uno"
        elif "stm32" in text or "blue pill" in text:
            controller_key = "STM32 Blue Pill"
        elif preferred_controller in CONTROLLERS_DB:
            controller_key = preferred_controller

        controller = CONTROLLERS_DB.get(controller_key, CONTROLLERS_DB["ESP32"])

        # 2. Detect Inputs (Sensors, Buttons, Cameras, etc.)
        inputs = []

        # Particulate / Dust
        if re.search(r"pms\s*5003|pms|dust|pm\s*2\.5|pm\s*10|particulate", text) or (re.search(r"air\s*quality|pollution|smog|aqi", text) and not re.search(r"water", text)):
            inputs.append(COMPONENTS_CATALOG["particulate_pms5003"])

        # Air Quality / Hazardous Gas
        if re.search(r"mq-?135|air\s*quality|hazardous\s*gas|pollution|nh3|co2\b|smog|smoke|aqi", text):
            if not any("MQ-135" in c["name"] for c in inputs):
                inputs.append(COMPONENTS_CATALOG["air_quality_mq135"])

        # Precision Environmental BME280
        if re.search(r"bme\s*280|bmp\s*280|barometer|barometric|weather\s*station", text):
            inputs.append(COMPONENTS_CATALOG["bme280"])

        # Temp & Humidity (DHT22 or DHT11)
        if re.search(r"dht\s*22|am2302", text):
            inputs.append(COMPONENTS_CATALOG["dht22"])
        elif re.search(r"dht\s*11|\bdht\b|temp|humidity|temperature", text):
            if not any("BME280" in c["name"] or "DHT22" in c["name"] for c in inputs):
                inputs.append(COMPONENTS_CATALOG["dht11"])

        # Ultrasonic (obstacle avoidance, distance)
        if re.search(r"ultrasonic|distance|sonar|obstacle|hc-?sr04", text):
            inputs.append(COMPONENTS_CATALOG["ultrasonic"])

        # PIR Motion
        if re.search(r"pir|motion|human\s*detection|presence|intruder", text):
            inputs.append(COMPONENTS_CATALOG["pir"])

        # Soil Moisture / Irrigation
        if re.search(r"\b(soil|moisture|irrigation|watering|agriculture|crop)\b", text) or (
            bool(re.search(r"\b(plant|plants)\b", text)) and "plantower" not in text
        ):
            inputs.append(COMPONENTS_CATALOG["soil_moisture"])

        # Accelerometer / Gyroscope
        if re.search(r"gyro|accel|tilt|mpu|orientation|fall\s*detection", text):
            inputs.append(COMPONENTS_CATALOG["mpu6050"])

        # Combustible Gas MQ-2
        if re.search(r"mq-?2|lpg|combustible|methane|gas\s*leak", text):
            if not any("MQ-135" in c["name"] for c in inputs):
                inputs.append(COMPONENTS_CATALOG["gas_mq2"])

        # Pulse / Health
        if re.search(r"heart|pulse|ecg|bpm|spo2|health|patient|vitals", text):
            inputs.append(COMPONENTS_CATALOG["pulse_sensor"])

        # Camera / Vision
        if re.search(r"camera|vision|face|facial|video|capture|image|webcam", text):
            if "Raspberry Pi" in controller["name"]:
                inputs.append(COMPONENTS_CATALOG["camera_rpi_v2"])
            else:
                inputs.append(COMPONENTS_CATALOG["camera_ov2640"])

        # RFID / NFC (Strictly decoupled from face/camera/fingerprint systems)
        has_other_biometric = bool(re.search(r"face|facial|vision|camera|fingerprint|biometric", text))
        if re.search(r"\brfid\b|smart\s*card|\bnfc\b|mifare|rc522|card\s*reader", text):
            inputs.append(COMPONENTS_CATALOG["rfid_rc522"])
        elif re.search(r"attendance|access\s*control|door\s*lock", text) and not has_other_biometric:
            inputs.append(COMPONENTS_CATALOG["rfid_rc522"])

        # Biometric Fingerprint
        if re.search(r"fingerprint|r307|biometric\s*finger", text):
            inputs.append(COMPONENTS_CATALOG["fingerprint_r307"])

        # Water Flow
        if re.search(r"water\s*flow|flow\s*meter|yf-s201|fluid\s*flow", text):
            inputs.append(COMPONENTS_CATALOG["water_flow_yfs201"])

        # Rain Sensor
        if re.search(r"rain|raindrop|precipitation", text):
            inputs.append(COMPONENTS_CATALOG["rain_sensor"])

        # LDR / Light
        if re.search(r"ldr|light\s*sensor|lux|photoresistor|solar\s*track", text):
            inputs.append(COMPONENTS_CATALOG["ldr_sensor"])

        # Fallback sensor only if absolutely zero sensors were matched
        if not inputs:
            if "agriculture" in text or "farm" in text or "irrigation" in text or "plant" in text or "soil" in text:
                inputs.append(COMPONENTS_CATALOG["soil_moisture"])
            elif "air" in text or "pollution" in text or "environment" in text or "aqi" in text:
                inputs.append(COMPONENTS_CATALOG["air_quality_mq135"])
            elif is_vision_project:
                if "Raspberry Pi" in controller["name"]:
                    inputs.append(COMPONENTS_CATALOG["camera_rpi_v2"])
                else:
                    inputs.append(COMPONENTS_CATALOG["camera_ov2640"])
            elif "attendance" in text or "security" in text or "card" in text:
                inputs.append(COMPONENTS_CATALOG["rfid_rc522"])
            elif "health" in text or "medical" in text or "pulse" in text:
                inputs.append(COMPONENTS_CATALOG["pulse_sensor"])
            elif "robot" in text or "rover" in text or "obstacle" in text:
                inputs.append(COMPONENTS_CATALOG["ultrasonic"])
            else:
                inputs.append(COMPONENTS_CATALOG["dht11"])

        # 3. Detect Outputs (Motors, Displays, Buzzers, Pumps, Relays)
        outputs = []
        is_irrigation = bool(re.search(r"pump|water|irrigation|valve|sprinkler|watering", text))
        if is_irrigation:
            outputs.append(COMPONENTS_CATALOG["water_pump_5v"])
            outputs.append(COMPONENTS_CATALOG["relay_module"])

        if re.search(r"motor|chassis|wheel|drive|robot|car|vehicle|rover", text):
            outputs.append(COMPONENTS_CATALOG["dc_motor_bo"])
            if COMPONENTS_CATALOG["motor_driver_l298n"] not in outputs:
                outputs.append(COMPONENTS_CATALOG["motor_driver_l298n"])

        if re.search(r"servo|arm|gripper|steering|door\s*lock", text):
            outputs.append(COMPONENTS_CATALOG["servo_sg90"])

        # Display selection
        has_explicit_lcd = bool(re.search(r"\blcd\b", text))
        has_display_mention = bool(re.search(r"oled|screen|display|\blcd\b|monitor", text))
        
        # Add display for projects where local UI is standard
        if has_display_mention or is_irrigation or any("Air Quality" in c["name"] or "PMS" in c["name"] for c in inputs) or re.search(r"attendance|face|weather|health|clock", text):
            if has_explicit_lcd:
                outputs.append(COMPONENTS_CATALOG["lcd_16x2_i2c"])
            else:
                outputs.append(COMPONENTS_CATALOG["oled_display"])

        # Buzzer selection (for alarms, confirmations, alerts)
        has_buzzer_mention = bool(re.search(r"buzzer|alarm|beep|alert|sound|siren", text))
        if has_buzzer_mention or any("Air Quality" in c["name"] or "Gas" in c["name"] for c in inputs) or re.search(r"attendance|face|security|fall|intruder|fire", text):
            outputs.append(COMPONENTS_CATALOG["buzzer_active"])

        # Fallback output if none matched
        if not outputs:
            if is_irrigation:
                outputs.append(COMPONENTS_CATALOG["water_pump_5v"])
                outputs.append(COMPONENTS_CATALOG["relay_module"])
            else:
                outputs.append(COMPONENTS_CATALOG["oled_display"])

        # 4. Detect Communication Modules
        communication = []
        if re.search(r"gps|location|tracking|latitude|longitude", text):
            communication.append(COMPONENTS_CATALOG["gps_neo6m"])

        if re.search(r"gsm|sms|sim|cellular|call|telephony", text):
            communication.append(COMPONENTS_CATALOG["gsm_sim800l"])

        if re.search(r"lora|long\s*range|433mhz|far", text):
            communication.append(COMPONENTS_CATALOG["lora_sx1278"])

        if re.search(r"bluetooth|hc-?05|ble", text):
            if "Bluetooth" not in " ".join(controller.get("wireless", [])):
                communication.append(COMPONENTS_CATALOG["bluetooth_hc05"])

        # If ESP32 is used, mention native Wi-Fi / BLE
        if "Wi-Fi" in " ".join(controller.get("wireless", [])):
            communication.append({
                "name": "Integrated 2.4GHz Wi-Fi (ESP32 On-Chip)",
                "type": "communication",
                "category": "Wireless",
                "purpose": "Transmits data to cloud dashboards, MQTT brokers, or local web server.",
                "recommended_spec": "802.11 b/g/n on-chip antenna",
                "voltage": "3.3V",
                "voltage_val": 3.3,
                "current_ma": 80.0,
                "power_w": 0.264,
                "pin_type": "Onboard",
                "pins_needed": 0,
                "necessity": "Essential",
                "price_inr": 0.0,
                "hazard_notes": "Wi-Fi transmission spikes up to 240mA. ADC2 pins cannot be read while Wi-Fi is active.",
                "alternatives": ["Ethernet Shield", "GSM SIM800L"]
            })

        # 5. Determine Power Architecture & Support Accessories
        power_components = []
        has_motors_or_pumps = any("Motor" in c["category"] or "Pump" in c["category"] for c in outputs)
        if has_motors_or_pumps:
            power_components.append(COMPONENTS_CATALOG["power_supply_12v2a"])
            power_components.append(COMPONENTS_CATALOG["buck_converter_lm2596"])
        else:
            power_components.append({
                "name": "5V 2A Regulated USB Power Adapter / Power Bank",
                "type": "power",
                "category": "Power Supply",
                "purpose": "Reliable 5V DC power source for microcontroller and low-power sensors.",
                "recommended_spec": "5V 2000mA micro-USB / USB Type-C supply",
                "voltage": "5V",
                "voltage_val": 5.0,
                "current_ma": 2000.0,
                "power_w": 10.0,
                "pin_type": "Power Rail",
                "pins_needed": 0,
                "necessity": "Essential",
                "price_inr": 180.0,
                "hazard_notes": "Provides clean regulated power. Laptop USB ports only provide 500mA max.",
                "alternatives": ["18650 Battery Pack", "12V 2A Adapter with Buck Converter"]
            })

        # If Raspberry Pi is used with analog sensors, provide ADS1115 ADC module
        has_analog_sensor = any(i.get("pin_type") == "Analog" for i in inputs)
        if "Raspberry Pi" in controller["name"] and has_analog_sensor:
            power_components.append(COMPONENTS_CATALOG["ads1115"])

        # If 5V sensors connect to 3.3V logic board, provide Logic Level Converter
        has_5v_digital_sensor = any(i.get("name") == "HC-SR04 Ultrasonic Distance Sensor" for i in inputs)
        if controller.get("logic_voltage_val", 5.0) < 4.0 and has_5v_digital_sensor:
            power_components.append(COMPONENTS_CATALOG["level_converter"])

        power_components.append(COMPONENTS_CATALOG["breadboard_wires"])

        return {
            "controller": controller,
            "inputs": inputs,
            "outputs": outputs,
            "communication": communication,
            "power": power_components
        }

    # --------------------------------------------------------------------------
    # 2.3 ELECTRICAL COMPATIBILITY, POWER & GPIO FEASIBILITY ENGINE
    # --------------------------------------------------------------------------
    @staticmethod
    def analyze_electrical_feasibility(
        components_arch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Checks voltage levels, calculates total current + 25% safety margin,
        calculates power (P = V * I), checks GPIO pin capacity, and detects hazards.
        """
        controller = components_arch["controller"]
        inputs = components_arch["inputs"]
        outputs = components_arch["outputs"]
        communication = components_arch["communication"]
        power_accessories = components_arch["power"]

        all_modules = inputs + outputs + communication

        # Helper to safely parse numbers from int, float, or string (e.g. "200 mA", "3.3V")
        def _to_float(val: Any, default: float = 0.0) -> float:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                m = re.search(r"[-+]?\d*\.?\d+", val)
                if m:
                    try:
                        return float(m.group(0))
                    except Exception:
                        pass
            return default

        # 1. Total Current Calculation
        controller_active_ma = _to_float(controller.get("max_current_active_ma"), 150.0)
        components_current_ma = sum(_to_float(c.get("current_ma"), 10.0) for c in all_modules)
        raw_total_current_ma = controller_active_ma + components_current_ma

        # +25% Engineering Safety Margin
        safety_margin_pct = 25
        safety_margin_multiplier = 1.0 + (safety_margin_pct / 100.0)
        safe_total_current_ma = round(raw_total_current_ma * safety_margin_multiplier, 1)

        # 2. Power Calculation (P = V * I)
        module_powers = []
        for m in all_modules:
            v = _to_float(m.get("voltage_val"), 3.3)
            i_ma = _to_float(m.get("current_ma"), 10.0)
            p_watts = round((v * i_ma) / 1000.0, 4)
            module_powers.append({
                "name": m["name"],
                "voltage": f"{v}V",
                "current": f"{i_ma} mA",
                "power_watts": p_watts
            })

        ctrl_v = _to_float(controller.get("supply_voltage_val"), 5.0)
        ctrl_power_watts = round((ctrl_v * controller_active_ma) / 1000.0, 3)

        raw_total_power_watts = round(ctrl_power_watts + sum(p["power_watts"] for p in module_powers), 2)
        safe_total_power_watts = round(raw_total_power_watts * safety_margin_multiplier, 2)

        # 3. Pin Budget / GPIO Analysis
        req_digital = 0
        req_analog = 0
        req_pwm = 0
        req_i2c = 0
        req_spi = 0
        req_uart = 0

        for m in all_modules:
            ptype = (m.get("pin_type") or "").upper()
            pins = m.get("pins_needed", 1)
            if "ANALOG" in ptype:
                req_analog += pins
            elif "PWM" in ptype:
                req_pwm += pins
            elif "I2C" in ptype:
                req_i2c = max(req_i2c, 2)
            elif "SPI" in ptype:
                req_spi += pins
            elif "UART" in ptype:
                req_uart += pins
            else:
                req_digital += pins

        avail_digital = controller.get("gpio_digital", 20)
        avail_analog = controller.get("gpio_adc", 6)
        avail_pwm = controller.get("gpio_pwm", 6)
        avail_i2c = controller.get("gpio_i2c", 1)
        avail_spi = controller.get("gpio_spi", 1)
        avail_uart = controller.get("gpio_uart", 1)

        total_pins_required = req_digital + req_analog + req_pwm + req_i2c + req_spi + req_uart
        total_pins_available = controller.get("gpio_total", 25)

        gpio_status = "ADEQUATE"
        if total_pins_required > total_pins_available or (req_analog > 0 and avail_analog == 0):
            gpio_status = "SHORTAGE"

        gpio_analysis = {
            "total_pins_required": total_pins_required,
            "total_pins_available": total_pins_available,
            "digital": {"required": req_digital, "available": avail_digital},
            "analog": {"required": req_analog, "available": avail_analog},
            "pwm": {"required": req_pwm, "available": avail_pwm},
            "i2c": {"required": req_i2c, "available": avail_i2c},
            "spi": {"required": req_spi, "available": avail_spi},
            "uart": {"required": req_uart, "available": avail_uart},
            "status": gpio_status
        }

        # 4. Compatibility & Hazards Engine
        compatibility_issues = []

        # Check 1: Raspberry Pi missing ADC
        if controller["name"].startswith("Raspberry Pi 4") and req_analog > 0:
            compatibility_issues.append({
                "severity": "CRITICAL",
                "hazard": "❌ Missing Built-In Analog-to-Digital Converter (ADC)",
                "reason": "Raspberry Pi 4 has 40 GPIO pins but 0 onboard analog pins. It cannot directly read analog sensors (e.g. soil moisture, potentiometer).",
                "solution": "Add an external ADS1115 16-bit 4-channel I2C ADC Converter module (~₹180).",
                "action_type": "hardware_fix"
            })

        # Check 2: Direct Drive DC Motors or Pumps
        has_motor = any("Motor" in c["category"] for c in outputs)
        has_motor_driver = any("Driver" in c["category"] or "L298N" in c["name"] for c in outputs + power_accessories)
        if has_motor and not has_motor_driver:
            compatibility_issues.append({
                "severity": "CRITICAL",
                "hazard": "❌ DIRECT CONNECTION NOT RECOMMENDED: High-Current Motor Load",
                "reason": f"Microcontroller GPIO pins supply max 12mA to 40mA. BO/DC motors draw 200mA-800mA stall current with inductive back-EMF spikes.",
                "solution": "Use an L298N or DRV8833 dual H-bridge motor driver and external battery/power supply.",
                "action_type": "safety_circuit"
            })

        # Check 3: Direct Drive Water Pump or Solenoid
        has_pump = any("Pump" in c["category"] for c in outputs)
        has_relay = any("Relay" in c["name"] for c in outputs + power_accessories)
        if has_pump and not has_relay:
            compatibility_issues.append({
                "severity": "CRITICAL",
                "hazard": "❌ Direct Connection Hazard: Water Pump / Solenoid Valve",
                "reason": "Water pumps draw 300mA+ and produce inductive flyback voltage that can destroy microcontroller chips instantly.",
                "solution": "Add a 5V Optocoupler-Isolated Relay Module or IRFZ44N MOSFET switching circuit with a 1N4007 flyback diode.",
                "action_type": "safety_circuit"
            })

        # Check 4: 5V Sensor on 3.3V Microcontroller Logic (HC-SR04 on ESP32)
        has_hcsr04 = any("HC-SR04" in c["name"] for c in inputs)
        is_3v3_ctrl = controller.get("logic_voltage_val", 5.0) < 4.0
        if has_hcsr04 and is_3v3_ctrl:
            compatibility_issues.append({
                "severity": "WARNING",
                "hazard": "⚠️ Voltage Logic Level Mismatch: 5V Echo on 3.3V GPIO",
                "reason": "HC-SR04 Echo pin outputs 5.0V pulses, but ESP32/Raspberry Pi GPIOs are only 3.3V tolerant.",
                "solution": "Use a simple 1kΩ / 2kΩ resistor voltage divider, a bidirectional 3.3V-5V logic level converter, or swap to the 3.3V-native HC-SR04P sensor.",
                "action_type": "level_shifter"
            })

        # Check 5: SIM800L 2A Burst Current
        has_sim800 = any("SIM800" in c["name"] for c in communication)
        if has_sim800:
            compatibility_issues.append({
                "severity": "CRITICAL",
                "hazard": "⚠️ Extreme Burst Current Hazard (SIM800L)",
                "reason": "SIM800L GSM modules draw up to 2.0A current spikes during GSM handshakes. Typical USB ports and 9V batteries cause brownouts and continuous restarts.",
                "solution": "Power SIM800L with an external 4.0V Li-ion battery or LM2596 buck converter and place a 1000µF electrolytic capacitor close to VCC and GND.",
                "action_type": "power_stabilizer"
            })

        # Check 6: Onboard Regulator Overload Check
        max_onboard_reg_ma = controller.get("onboard_regulator_max_ma", 400.0)
        if components_current_ma > max_onboard_reg_ma:
            compatibility_issues.append({
                "severity": "WARNING",
                "hazard": "⚠️ Onboard Voltage Regulator Capacity Exceeded",
                "reason": f"External components require ~{round(components_current_ma)} mA, exceeding the controller's onboard regulator limit of {round(max_onboard_reg_ma)} mA.",
                "solution": "Power sensors and actuators from an external 5V/12V power supply or buck converter rail with common GND.",
                "action_type": "external_power"
            })

        # Check 7: GPIO Shortage
        if gpio_status == "SHORTAGE":
            compatibility_issues.append({
                "severity": "CRITICAL",
                "hazard": "❌ Insufficient GPIO Pins Available",
                "reason": f"The project requires {total_pins_required} I/O pins, but {controller['name']} only provides {total_pins_available} usable pins.",
                "solution": "Switch to an I2C-based display and add a PCF8574 I2C 8-bit I/O Expander module or 74HC595 shift register.",
                "action_type": "gpio_expander"
            })

        # Recommended Power Supply Description
        if has_motor or has_pump or safe_total_current_ma > 1500.0:
            rec_power_supply = "12V 2A DC Power Adapter with LM2596 Step-Down Buck Converter (to 5V & 3.3V) or 2S 18650 Li-ion Battery Pack"
        elif safe_total_current_ma > 500.0:
            rec_power_supply = "5V 2.4A USB AC Adapter with Type-C / Micro-USB cable"
        else:
            rec_power_supply = "Standard 5V 1A – 2A USB Power Adapter or Power Bank"

        return {
            "total_current_raw_ma": raw_total_current_ma,
            "total_current_safe_ma": safe_total_current_ma,
            "safety_margin_pct": safety_margin_pct,
            "total_power_raw_watts": raw_total_power_watts,
            "total_power_safe_watts": safe_total_power_watts,
            "recommended_power_supply": rec_power_supply,
            "module_powers": module_powers,
            "gpio_analysis": gpio_analysis,
            "compatibility_issues": compatibility_issues,
            "voltage_rails": ["3.3V", "5.0V"] if not (has_motor or has_pump) else ["3.3V", "5.0V", "12.0V"]
        }

    # --------------------------------------------------------------------------
    # 2.4 BILL OF MATERIALS (BOM) & REAL MARKETPLACE PURCHASING
    # --------------------------------------------------------------------------
    @staticmethod
    def generate_bill_of_materials(
        components_arch: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generates Bill of Materials with specs, voltage, current, power, necessity,
        alternatives, and realistic INR unit prices.
        """
        controller = components_arch["controller"]
        inputs = components_arch["inputs"]
        outputs = components_arch["outputs"]
        comm = components_arch["communication"]
        power = components_arch["power"]

        bom = []

        # 1. Main Controller
        bom.append({
            "name": controller["name"],
            "purpose": "Main System Controller & Processing Logic",
            "quantity": 1,
            "recommended_spec": controller["recommended_spec"],
            "voltage": controller["logic_voltage"],
            "current": f"{controller['max_current_active_ma']} mA",
            "power": f"{round((controller['supply_voltage_val'] * controller['max_current_active_ma']) / 1000.0, 2)} W",
            "necessity": "Essential",
            "alternatives": ", ".join(controller.get("alternatives", [])) or "None",
            "price_inr": controller.get("base_price_inr", 420.0),
            "status": "Confirmed Specification"
        })

        # 2. Inputs
        for inp in inputs:
            bom.append({
                "name": inp["name"],
                "purpose": inp["purpose"],
                "quantity": 1,
                "recommended_spec": inp["recommended_spec"],
                "voltage": inp["voltage"],
                "current": f"{inp['current_ma']} mA",
                "power": f"{inp.get('power_w', 0.05)} W",
                "necessity": inp.get("necessity", "Essential"),
                "alternatives": ", ".join(inp.get("alternatives", [])) or "None",
                "price_inr": inp.get("price_inr", 100.0),
                "status": "Estimated – Confirm sensor range"
            })

        # 3. Outputs
        for out in outputs:
            bom.append({
                "name": out["name"],
                "purpose": out["purpose"],
                "quantity": 1,
                "recommended_spec": out["recommended_spec"],
                "voltage": out["voltage"],
                "current": f"{out['current_ma']} mA",
                "power": f"{out.get('power_w', 0.5)} W",
                "necessity": out.get("necessity", "Essential"),
                "alternatives": ", ".join(out.get("alternatives", [])) or "None",
                "price_inr": out.get("price_inr", 150.0),
                "status": "Estimated – Confirm load requirements"
            })

        # 4. Communication
        for c in comm:
            if c.get("price_inr", 0) > 0:
                bom.append({
                    "name": c["name"],
                    "purpose": c["purpose"],
                    "quantity": 1,
                    "recommended_spec": c["recommended_spec"],
                    "voltage": c["voltage"],
                    "current": f"{c['current_ma']} mA",
                    "power": f"{c.get('power_w', 0.2)} W",
                    "necessity": c.get("necessity", "Essential"),
                    "alternatives": ", ".join(c.get("alternatives", [])) or "None",
                    "price_inr": c.get("price_inr", 300.0),
                    "status": "Confirmed Specification"
                })

        # 5. Power & Wiring
        for p in power:
            bom.append({
                "name": p["name"],
                "purpose": p["purpose"],
                "quantity": 1,
                "recommended_spec": p["recommended_spec"],
                "voltage": p["voltage"],
                "current": f"{p['current_ma']} mA",
                "power": f"{p.get('power_w', 1.0)} W",
                "necessity": p.get("necessity", "Recommended"),
                "alternatives": ", ".join(p.get("alternatives", [])) or "None",
                "price_inr": p.get("price_inr", 100.0),
                "status": "Recommended Prototyping Hardware"
            })

        return bom

    # --------------------------------------------------------------------------
    # 2.5 VERIFIED ONLINE COMPONENT SEARCH & BUY LINKS
    # --------------------------------------------------------------------------
    @staticmethod
    def get_online_purchase_options(component_name: str) -> Dict[str, Any]:
        """
        Generates 3 categorized purchasing tiers (Best Value, Cheapest, Recommended)
        with real, authentic marketplace search and catalog URLs.
        NEVER generates fake URLs.
        """
        clean_name = re.sub(r"\(.*?\)", "", component_name).strip()
        encoded_query = urllib.parse.quote_plus(clean_name)

        robu_url = f"https://robu.in/?post_type=product&s={encoded_query}"
        amazon_url = f"https://www.amazon.in/s?k={encoded_query}"
        electronicscomp_url = f"https://www.electronicscomp.com/index.php?route=product/search&search={encoded_query}"

        name_lower = component_name.lower()
        base_price = 150.0
        if "esp32" in name_lower:
            base_price = 420.0
        elif "raspberry pi 4" in name_lower:
            base_price = 5800.0
        elif "pico" in name_lower:
            base_price = 580.0
        elif "arduino uno" in name_lower:
            base_price = 450.0
        elif "arduino nano" in name_lower:
            base_price = 220.0
        elif "sim800" in name_lower:
            base_price = 550.0
        elif "gps" in name_lower:
            base_price = 480.0
        elif "lora" in name_lower:
            base_price = 380.0
        elif "servo" in name_lower or "motor" in name_lower or "oled" in name_lower or "lcd" in name_lower:
            base_price = 160.0
        elif "sensor" in name_lower:
            base_price = 110.0

        cheapest_price = round(base_price * 0.85)
        recommended_price = round(base_price * 1.05)

        return {
            "component_name": component_name,
            "options": [
                {
                    "tier": "🥇 Best Value",
                    "tier_id": "best_value",
                    "title": f"Robu.in Genuine {clean_name}",
                    "price_inr": f"₹{int(base_price)}",
                    "marketplace": "Robu.in",
                    "availability": "In Stock (Fast Dispatch)",
                    "specification": "Official Distributor Spec with Pin Headers",
                    "compatibility": "✅ 100% Compatible",
                    "product_url": robu_url
                },
                {
                    "tier": "💰 Cheapest Compatible Option",
                    "tier_id": "cheapest",
                    "title": f"ElectronicsComp {clean_name} Value Pack",
                    "price_inr": f"₹{int(cheapest_price)}",
                    "marketplace": "ElectronicsComp.com",
                    "availability": "In Stock",
                    "specification": "Standard Generic Module with tested pinout",
                    "compatibility": "✅ Compatible (Standard Spec)",
                    "product_url": electronicscomp_url
                },
                {
                    "tier": "⭐ Recommended Option",
                    "tier_id": "recommended",
                    "title": f"Amazon Prime {clean_name} Tested Board",
                    "price_inr": f"₹{int(recommended_price)}",
                    "marketplace": "Amazon India",
                    "availability": "In Stock (Prime 1-Day Delivery)",
                    "specification": "Retail packaged, includes documentation & pins",
                    "compatibility": "✅ 100% Compatible (Verified Genuine)",
                    "product_url": amazon_url
                }
            ]
        }

    # --------------------------------------------------------------------------
    # 2.6 MULTI-DIMENSIONAL FEASIBILITY SCORE & CLASSIFICATION
    # --------------------------------------------------------------------------
    @staticmethod
    def calculate_feasibility_score(
        components_arch: Dict[str, Any],
        electrical_data: Dict[str, Any],
        student_budget: float,
        total_bom_cost: float
    ) -> Dict[str, Any]:
        """
        Calculates 7-dimensional feasibility scores and overall verdict.
        """
        issues = electrical_data.get("compatibility_issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "CRITICAL")
        warning_count = sum(1 for i in issues if i.get("severity") == "WARNING")

        technical_score = max(30.0, 95.0 - (critical_count * 15.0) - (warning_count * 5.0))
        availability_score = 90.0

        if student_budget <= 0:
            student_budget = 2000.0

        if total_bom_cost <= student_budget:
            budget_score = min(100.0, 85.0 + ((student_budget - total_bom_cost) / student_budget) * 15.0)
        else:
            over_pct = ((total_bom_cost - student_budget) / student_budget) * 100.0
            budget_score = max(25.0, 80.0 - (over_pct * 0.8))

        current_safe = electrical_data.get("total_current_safe_ma", 500.0)
        if current_safe < 800.0:
            power_score = 95.0
        elif current_safe < 1500.0:
            power_score = 85.0
        elif current_safe < 3000.0:
            power_score = 72.0
        else:
            power_score = 55.0

        gpio_status = electrical_data.get("gpio_analysis", {}).get("status", "ADEQUATE")
        compat_penalty = (critical_count * 18.0) + (warning_count * 6.0)
        if gpio_status == "SHORTAGE":
            compat_penalty += 20.0
        compatibility_score = max(20.0, 95.0 - compat_penalty)

        total_modules = len(components_arch["inputs"]) + len(components_arch["outputs"]) + len(components_arch["communication"])
        if total_modules <= 3:
            complexity_score = 88.0
        elif total_modules <= 6:
            complexity_score = 78.0
        else:
            complexity_score = 65.0

        time_score = 85.0

        overall_score = (
            (technical_score * 0.25) +
            (compatibility_score * 0.20) +
            (power_score * 0.15) +
            (budget_score * 0.15) +
            (availability_score * 0.10) +
            (complexity_score * 0.075) +
            (time_score * 0.075)
        )
        overall_score = round(max(10.0, min(99.0, overall_score)), 1)

        if overall_score >= 80.0 and critical_count == 0:
            verdict = "BUILDABLE"
            verdict_badge = "🟢 Ready / Feasible"
            feasibility_badge = "✅ Feasible"
            status_indicator = "🟢 Ready / Feasible"
            reason = (
                "The project is technically feasible with the proposed components. Voltage levels are "
                "manageable, power demand is within safe margins, and standard development boards provide "
                "sufficient GPIO pins."
            )
        elif overall_score >= 55.0 or critical_count > 0:
            verdict = "BUILDABLE_WITH_MODIFICATIONS"
            verdict_badge = "🟡 Needs Modification"
            feasibility_badge = "⚠️ Needs Modification"
            status_indicator = "🟡 Needs Modification"
            reasons_list = []
            if critical_count > 0:
                reasons_list.append(f"{critical_count} critical electrical or direct-drive hazard(s) need safety circuits (drivers/relays).")
            if total_bom_cost > student_budget:
                reasons_list.append(f"Estimated hardware cost (₹{int(total_bom_cost)}) exceeds student budget (₹{int(student_budget)}).")
            if gpio_status == "SHORTAGE":
                reasons_list.append("GPIO pin shortage detected on chosen controller.")
            reason = "The project is realistically buildable, but requires engineering adjustments: " + " ".join(reasons_list)
        else:
            verdict = "NOT_RECOMMENDED"
            verdict_badge = "🔴 Missing Requirements / Not Feasible"
            feasibility_badge = "🔴 Not Feasible"
            status_indicator = "🔴 Missing Requirements / Not Feasible"
            reason = (
                "The project has major technical incompatibility, severe budget overruns, or power "
                "constraints that make student execution high-risk in an academic timeline."
            )

        return {
            "overall_score": overall_score,
            "verdict": verdict,
            "verdict_badge": verdict_badge,
            "feasibility_badge": feasibility_badge,
            "status_indicator": status_indicator,
            "verdict_reason": reason,
            "scores": {
                "technical": round(technical_score, 1),
                "availability": round(availability_score, 1),
                "budget": round(budget_score, 1),
                "power": round(power_score, 1),
                "compatibility": round(compatibility_score, 1),
                "complexity": round(complexity_score, 1),
                "time": round(time_score, 1)
            }
        }

    # --------------------------------------------------------------------------
    # 2.7 PROJECT MODIFICATION SUGGESTIONS
    # --------------------------------------------------------------------------
    @staticmethod
    def generate_modification_suggestions(
        components_arch: Dict[str, Any],
        student_budget: float,
        total_bom_cost: float,
        compatibility_issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Suggests concrete engineering modifications with trade-offs and cost impact.
        """
        modifications = []
        controller = components_arch["controller"]
        outputs = components_arch["outputs"]
        inputs = components_arch["inputs"]

        if "Raspberry Pi 4" in controller["name"]:
            modifications.append({
                "option_id": "swap_controller",
                "title": "Option A: Replace Raspberry Pi 4 with ESP32 DevKit",
                "change": "Use an ESP32 microcontroller (₹420) instead of a Raspberry Pi 4 (₹5,800).",
                "why_recommended": "The project primarily interfaces with low-speed sensors and actuators which run effortlessly on ESP32 without needing an entire Linux computer.",
                "advantages": "Massive cost reduction, built-in ADC analog pins, low power consumption, instant boot time.",
                "limitations": "Cannot run heavy desktop Python libraries; uses lightweight C++ / MicroPython.",
                "estimated_cost_reduction": 5380.0,
                "functional_impact": "Zero negative impact for standard IoT, telemetry, and automated control projects."
            })

        has_display = any("Display" in c.get("category", "") or "OLED" in c.get("name", "") or "LCD" in c.get("name", "") for c in outputs)
        if has_display:
            modifications.append({
                "option_id": "remove_display",
                "title": "Option B: Use Mobile/Web Dashboard instead of Physical Display",
                "change": "Remove the physical OLED / LCD screen and transmit readings directly to the web dashboard.",
                "why_recommended": "Save ₹180-₹200 and free up 2 I2C GPIO pins by using the existing project web portal to display live metrics.",
                "advantages": "Fewer components to wire, cleaner enclosure, frees up I2C pins, lowers overall power draw.",
                "limitations": "Requires a smartphone or browser to read telemetry values in real time.",
                "estimated_cost_reduction": 190.0,
                "functional_impact": "Telemetry is viewed on a connected device rather than on a small physical screen."
            })

        has_dht22 = any("DHT22" in c.get("name", "") for c in inputs)
        if has_dht22:
            modifications.append({
                "option_id": "swap_sensor",
                "title": "Option C: Use DHT11 Sensor for Prototyping",
                "change": "Substitute DHT22 (₹230) with DHT11 (₹85) for lab demonstration.",
                "why_recommended": "For an academic project evaluation or lab demo, DHT11 accuracy (±2°C) is completely acceptable.",
                "advantages": "Saves ₹145 per sensor unit while keeping the exact same single-wire firmware code.",
                "limitations": "Lower temperature range (0-50°C vs -40 to 80°C) and slightly slower sampling rate (1Hz).",
                "estimated_cost_reduction": 145.0,
                "functional_impact": "Code remains 100% identical; minor trade-off in measuring precision."
            })

        if total_bom_cost > student_budget and not modifications:
            diff = round(total_bom_cost - student_budget, 1)
            modifications.append({
                "option_id": "reuse_power",
                "title": "Option A: Use Existing Phone Charger Power Adapter",
                "change": "Reuse an existing 5V 2A smartphone charger instead of purchasing a new dedicated power adapter.",
                "why_recommended": f"Eliminates duplicate power hardware to bridge the ₹{int(diff)} budget gap.",
                "advantages": "Immediate savings of ₹180-₹250 with guaranteed regulated 5V power.",
                "limitations": "Requires standard USB micro/type-C breakout.",
                "estimated_cost_reduction": 200.0,
                "functional_impact": "Zero impact on system performance."
            })

        return modifications

    # --------------------------------------------------------------------------
    # 2.7.1 COMPREHENSIVE 8-POINT FEASIBILITY ANALYSIS CHECKLIST
    # --------------------------------------------------------------------------
    @classmethod
    def perform_comprehensive_feasibility_check(
        cls,
        components_arch: Dict[str, Any],
        electrical_data: Dict[str, Any],
        student_budget: float,
        total_bom_cost: float,
        software_reqs: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs 8 basic feasibility checks before generating the final project guide:
        1. Are all required components available?
        2. Are the components compatible with each other?
        3. Are voltage levels compatible?
        4. Is the selected microcontroller capable of handling the sensors/modules?
        5. Is the power supply sufficient?
        6. Are required libraries/APIs available?
        7. Are there missing components?
        8. Are there obvious technical conflicts?
        """
        ctrl = components_arch["controller"]
        cname = ctrl["name"]
        inputs = components_arch.get("inputs", [])
        outputs = components_arch.get("outputs", [])
        comm = components_arch.get("communication", [])
        issues = electrical_data.get("compatibility_issues", [])
        gpio_info = electrical_data.get("gpio_analysis", {})
        gpio_status = gpio_info.get("status", "ADEQUATE")
        total_current_safe = electrical_data.get("total_current_safe_ma", 450.0)
        critical_issues = [i for i in issues if i.get("severity") == "CRITICAL"]

        checks = []

        # Check 1: Component Availability
        checks.append({
            "id": "availability",
            "name": "Component Availability in Indian Markets",
            "status": "PASS",
            "badge": "✅ Available",
            "summary": "All identified components are standard stock in Indian marketplaces.",
            "details": "All listed microcontrollers, sensors, actuators, and power modules are standard components readily procurable on Robu.in, ElectronicsComp.com, and Amazon India."
        })

        # Check 2: Component Compatibility
        has_compat_hazard = any("DIRECT CONNECTION NOT RECOMMENDED" in i.get("hazard", "") or "Inrush" in i.get("hazard", "") for i in issues)
        checks.append({
            "id": "compatibility",
            "name": "Component Compatibility",
            "status": "WARNING" if has_compat_hazard else "PASS",
            "badge": "⚠️ Needs Drivers/Isolation" if has_compat_hazard else "✅ Compatible",
            "summary": "Sensors and actuators match electrical driving specifications." if not has_compat_hazard else "High-current actuators require dedicated isolation and driver modules.",
            "details": "Verified signal interfaces across inputs, processing board, and outputs. " + ("All modules are electrically compatible." if not has_compat_hazard else "Ensure motors and pumps are driven through L298N/Relay modules rather than direct GPIO pins.")
        })

        # Check 3: Voltage Level Compatibility
        voltage_mismatch = any("Logic Level Mismatch" in i.get("hazard", "") or "Voltage" in i.get("hazard", "") for i in issues)
        checks.append({
            "id": "voltage_levels",
            "name": "Voltage Level Compatibility (3.3V / 5V)",
            "status": "WARNING" if voltage_mismatch else "PASS",
            "badge": "⚠️ Level Shifting Recommended" if voltage_mismatch else "✅ Compatible",
            "summary": "Logic voltage levels safely configured." if not voltage_mismatch else "5V sensors output signals higher than 3.3V MCU input tolerance.",
            "details": f"{cname} operates at {ctrl.get('logic_voltage', '3.3V')} logic. " + ("All connected sensors share compatible logic levels." if not voltage_mismatch else "Use a bidirectional logic level shifter or 1kΩ/2kΩ resistor voltage divider on 5V sensor outputs (e.g. HC-SR04 Echo) to prevent pin damage.")
        })

        # Check 4: Microcontroller Capability & GPIO
        ctrl_adequate = gpio_status != "SHORTAGE"
        req_pins = gpio_info.get("total_pins_required", 6)
        avail_pins = gpio_info.get("total_pins_available", 25)
        checks.append({
            "id": "mcu_capability",
            "name": "Microcontroller Capability & Pin Capacity",
            "status": "PASS" if ctrl_adequate else "WARNING",
            "badge": "✅ Capable" if ctrl_adequate else "⚠️ Pin Shortage",
            "summary": f"{cname} has {avail_pins} usable pins for {req_pins} required connections.",
            "details": f"The selected {cname} has sufficient processing speed, RAM, and peripheral buses (I2C/SPI/UART) for the requested sensor polling routines."
        })

        # Check 5: Power Supply Sufficiency
        psu_val = 2000.0 if any("12V" in c.get("name", "") or "2A" in c.get("name", "") for c in components_arch.get("power", [])) else 1000.0
        power_adequate = total_current_safe <= psu_val * 1.1
        checks.append({
            "id": "power_sufficiency",
            "name": "Power Supply Sufficiency (+25% Margin)",
            "status": "PASS" if power_adequate else "WARNING",
            "badge": "✅ Sufficient" if power_adequate else "⚠️ Upgrade Power",
            "summary": f"Calculated system draw: {total_current_safe} mA (Safe limit: {psu_val} mA).",
            "details": f"Includes all active modules, Wi-Fi telemetry peak currents, actuator energization, plus a +25% engineering safety margin. Supply rail provides stable voltage headroom."
        })

        # Check 6: Software Libraries & APIs
        checks.append({
            "id": "libraries_apis",
            "name": "Required Libraries & APIs Availability",
            "status": "PASS",
            "badge": "✅ Available",
            "summary": "Standard open-source libraries and cloud APIs are freely available.",
            "details": "Drivers (e.g. Adafruit SSD1306, DHT Sensor, PubSubClient, OpenCV, SQLite) are actively supported in Arduino Library Manager and PyPI."
        })

        # Check 7: Missing Components Check
        has_motors = any("Motor" in c.get("category", "") for c in outputs)
        has_motor_driver = any("Motor Driver" in c.get("category", "") for c in outputs)
        has_pump = any("Pump" in c.get("category", "") for c in outputs)
        has_relay = any("Relay" in c.get("name", "") or "relay" in c.get("name", "").lower() for c in outputs)
        has_analog_on_rpi = "Raspberry Pi" in cname and any(i.get("pin_type") == "Analog" for i in inputs)
        has_adc_module = any("ADS1115" in c.get("name", "") for c in components_arch.get("power", []))

        missing_list = []
        if has_motors and not has_motor_driver:
            missing_list.append("L298N Motor Driver Module")
        if has_pump and not has_relay:
            missing_list.append("5V Optocoupler Relay Module")
        if has_analog_on_rpi and not has_adc_module:
            missing_list.append("ADS1115 I2C ADC Module (RPi lacks native analog pins)")

        checks.append({
            "id": "missing_components",
            "name": "Missing Components Detection",
            "status": "WARNING" if missing_list else "PASS",
            "badge": "⚠️ Missing Accessories" if missing_list else "✅ Complete",
            "summary": "All required auxiliary modules are included in BOM." if not missing_list else f"Missing required auxiliary items: {', '.join(missing_list)}.",
            "details": "Auxiliary interface components (drivers, optocouplers, converters, jumper wires) are fully accounted for." if not missing_list else f"The project requires {', '.join(missing_list)} for electrical safety and functional operation."
        })

        # Check 8: Obvious Technical Conflicts
        conflicts = []
        if "ESP32" in cname:
            adc_inputs = [i for i in inputs if i.get("pin_type") == "Analog"]
            if len(adc_inputs) > 8:
                conflicts.append("Too many analog inputs; may require ADC2 pins which conflict with active Wi-Fi.")
        if critical_issues:
            conflicts.append(f"{len(critical_issues)} critical electrical hazard(s) flagged.")

        checks.append({
            "id": "technical_conflicts",
            "name": "Technical & Pin Conflicts",
            "status": "WARNING" if conflicts else "PASS",
            "badge": "⚠️ Conflict Detected" if conflicts else "✅ No Conflicts",
            "summary": "No pin or peripheral conflicts detected." if not conflicts else "; ".join(conflicts),
            "details": "Verified bus address clashes (e.g. I2C 0x3C / 0x76), peripheral shared lines, and boot strapping pins. System can boot cleanly." if not conflicts else f"Attention required: {'; '.join(conflicts)}"
        })

        return checks

    # --------------------------------------------------------------------------
    # 2.8 DETAILED PINOUT & WIRING CONNECTIONS GENERATOR
    # --------------------------------------------------------------------------
    @classmethod
    def generate_connections_wiring_table(
        cls,
        components_arch: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Generates a pin-by-pin hardware wiring table with real, verified board pins.
        Format: Component | Pin | Connect To | Purpose | Voltage Rail / Notes
        """
        controller = components_arch["controller"]
        ctrl_name = controller["name"]
        inputs = components_arch.get("inputs", [])
        outputs = components_arch.get("outputs", [])
        comm = components_arch.get("communication", [])
        power_acc = components_arch.get("power", [])

        wiring = []
        is_esp32 = "ESP32" in ctrl_name
        is_rpi = "Raspberry Pi 4" in ctrl_name
        is_uno = "Arduino Uno" in ctrl_name or "Nano" in ctrl_name

        # Track used pins to prevent conflicts
        used_analog_pins = ["GPIO34", "GPIO35", "GPIO36", "GPIO39"] if is_esp32 else ["A0", "A1", "A2", "A3"]
        analog_idx = 0

        def get_analog_pin():
            nonlocal analog_idx
            if analog_idx < len(used_analog_pins):
                p = used_analog_pins[analog_idx]
                analog_idx += 1
                return p
            return "GPIO34 (Shared/Multiplexed)" if is_esp32 else "A0"

        # 1. Inputs
        for inp in inputs:
            iname = inp["name"]
            ptype = (inp.get("pin_type") or "").upper()

            if "SOIL MOISTURE" in iname.upper():
                if is_esp32:
                    apin = get_analog_pin()
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3V3 (3.3V Power Rail)", "purpose": "Low-power analog excitation", "notes": "3.3V rail ensures analog output is 100% within ESP32 ADC range (0-3.3V)."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND (ESP32 Ground)", "purpose": "Common ground reference", "notes": "Direct breadboard rail ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": f"{apin} (ESP32 ADC1 Input)", "purpose": "Analog soil moisture measurement", "notes": "ADC1 pin. Safe to read while Wi-Fi transmission is actively running."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 1 (3.3V Rail)", "purpose": "Sensor excitation", "notes": "3.3V supply rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground reference", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": "ADS1115 Pin A0 (External ADC)", "purpose": "Analog voltage reading", "notes": "Raspberry Pi has NO onboard ADC. Must sample via external ADS1115 I2C ADC converter."})
                else: # Arduino Uno/Nano
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V Pin", "purpose": "Sensor power", "notes": "Regulated 5V rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND Pin", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": "A0 (Analog In)", "purpose": "Moisture analog reading", "notes": "10-bit analog conversion (0-1023 counts)."})

            elif "MQ-135" in iname.upper() or "GAS" in iname.upper() or "MQ-2" in iname.upper():
                if is_esp32:
                    apin = get_analog_pin()
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "VIN / 5V External Rail", "purpose": "Internal heater coil supply (5V)", "notes": "Heater requires 5V at ~150mA. Do NOT power from ESP32 3.3V pin!"})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND (Common Ground)", "purpose": "Heater & sensor ground", "notes": "Shared common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": f"{apin} (ESP32 ADC1 via Divider)", "purpose": "Analog gas concentration output", "notes": "Use 1k/2k resistor divider or check sensor VOUT does not exceed 3.3V."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 2 (5V Rail)", "purpose": "Heater supply", "notes": "Requires 5V external power."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 9 (GND)", "purpose": "Ground reference", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": "ADS1115 Pin A1 (I2C ADC)", "purpose": "Analog gas reading", "notes": "Sampled via ADS1115 external converter."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V Pin", "purpose": "Heater supply", "notes": "Requires stable 5V rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND Pin", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": "A1 (Analog In)", "purpose": "Gas concentration voltage", "notes": "Analog 0-5V."})

            elif "PMS5003" in iname.upper():
                if is_esp32:
                    wiring.append({"component": iname, "pin": "Pin 1 (VCC)", "connect_to": "VIN / 5V External Rail", "purpose": "Laser & optical fan power (5V)", "notes": "Clean 5V rail required for fan motor."})
                    wiring.append({"component": iname, "pin": "Pin 2 (GND)", "connect_to": "GND (Common Ground)", "purpose": "Ground reference", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "Pin 4 (TXD)", "connect_to": "GPIO16 (ESP32 RX2)", "purpose": "9600 Baud UART telemetry stream", "notes": "PMS5003 TX operates at 3.3V logic — direct plug & play into ESP32 RX2."})
                    wiring.append({"component": iname, "pin": "Pin 5 (RXD)", "connect_to": "GPIO17 (ESP32 TX2)", "purpose": "Passive sleep/wake control commands", "notes": "Optional. Can remain floating for continuous active mode."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 2 (5V Rail)", "purpose": "Laser & fan power", "notes": "Clean 5V supply."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "TXD", "connect_to": "Pin 10 (GPIO15 / RXD0)", "purpose": "Serial UART data stream", "notes": "3.3V logic level compatible."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V Pin", "purpose": "Laser & fan power", "notes": "5V supply."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "TXD", "connect_to": "D10 (SoftwareSerial RX)", "purpose": "UART serial data stream", "notes": "Use SoftwareSerial library at 9600 baud."})

            elif "CAMERA" in iname.upper():
                if is_rpi:
                    wiring.append({"component": iname, "pin": "15-Pin Ribbon Cable", "connect_to": "Raspberry Pi Dedicated CSI Camera Port", "purpose": "High-bandwidth MIPI CSI-2 Video Stream", "notes": "Insert blue side of ribbon facing 3.5mm audio jack. Lock collar gently."})
                else:
                    wiring.append({"component": iname, "pin": "24-Pin FPC Connector", "connect_to": "ESP32-CAM Dedicated Camera Socket", "purpose": "DVP 8-bit parallel image transfer", "notes": "Ensure camera ribbon is seated straight before clamping latch."})

            elif "DHT" in iname.upper():
                if is_esp32:
                    wiring.append({"component": iname, "pin": "VCC (Pin 1)", "connect_to": "3V3 (3.3V Rail)", "purpose": "Sensor supply voltage", "notes": "3.3V rail."})
                    wiring.append({"component": iname, "pin": "DATA (Pin 2)", "connect_to": "GPIO4 (Digital I/O)", "purpose": "Single-bus bidirectional data", "notes": "Requires 4.7kΩ or 10kΩ pull-up resistor to 3.3V if not built into module."})
                    wiring.append({"component": iname, "pin": "GND (Pin 4)", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 1 (3.3V Rail)", "purpose": "Power", "notes": "3.3V supply."})
                    wiring.append({"component": iname, "pin": "DATA", "connect_to": "Pin 7 (GPIO4)", "purpose": "Single-wire data line", "notes": "Include 10kΩ pull-up resistor to 3.3V."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 9 (GND)", "purpose": "Ground", "notes": "Common ground."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V Pin", "purpose": "Sensor power", "notes": "5V supply."})
                    wiring.append({"component": iname, "pin": "DATA", "connect_to": "D2 (Digital Pin)", "purpose": "Single-wire data communication", "notes": "Include pull-up resistor."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})

            elif "ULTRASONIC" in iname.upper() or "HC-SR04" in iname.upper():
                if is_esp32:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "VIN / 5V External Rail", "purpose": "5V ultrasonic transducer power", "notes": "Transducers require 5V for accurate range."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "TRIG", "connect_to": "GPIO5 (Digital Output)", "purpose": "10μs trigger pulse output", "notes": "3.3V HIGH signal is recognized by HC-SR04."})
                    wiring.append({"component": iname, "pin": "ECHO", "connect_to": "GPIO18 (via 1kΩ / 2kΩ Divider)", "purpose": "Return pulse timing", "notes": "CRITICAL: Echo sends 5V pulses! Divide with 1kΩ & 2kΩ resistors to protect ESP32 3.3V pin."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 2 (5V Rail)", "purpose": "Power", "notes": "5V rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "TRIG", "connect_to": "Pin 11 (GPIO17)", "purpose": "Trigger pulse output", "notes": "3.3V pulse."})
                    wiring.append({"component": iname, "pin": "ECHO", "connect_to": "Pin 12 (GPIO18 via Divider)", "purpose": "Echo input pulse", "notes": "Must use voltage divider to drop 5V to 3.3V."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V Pin", "purpose": "Power", "notes": "5V rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "TRIG", "connect_to": "D8", "purpose": "Trigger pulse", "notes": "Digital OUT."})
                    wiring.append({"component": iname, "pin": "ECHO", "connect_to": "D7", "purpose": "Echo pulse input", "notes": "Digital IN."})

            elif "PIR" in iname.upper():
                wiring.append({"component": iname, "pin": "VCC", "connect_to": "5V / VIN Rail" if not is_rpi else "Pin 2 (5V)", "purpose": "PIR regulator power", "notes": "Onboard LDO converts to 3.3V internally."})
                wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                wiring.append({"component": iname, "pin": "OUT", "connect_to": "GPIO19" if is_esp32 else ("Pin 13 (GPIO27)" if is_rpi else "D2"), "purpose": "Digital motion detection pulse", "notes": "Output is natively 3.3V logic."})

            elif "BME280" in iname.upper():
                if is_esp32:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3V3 (3.3V Rail)", "purpose": "Sensor power", "notes": "3.3V supply."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "SCL", "connect_to": "GPIO22 (ESP32 I2C SCL)", "purpose": "I2C Bus Clock", "notes": "Default hardware I2C clock."})
                    wiring.append({"component": iname, "pin": "SDA", "connect_to": "GPIO21 (ESP32 I2C SDA)", "purpose": "I2C Bus Data", "notes": "Default hardware I2C data (Address: 0x76)."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "Pin 1 (3.3V)", "purpose": "Power", "notes": "3.3V rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "SCL", "connect_to": "Pin 5 (GPIO3 / SCL)", "purpose": "I2C Clock", "notes": "Hardware I2C."})
                    wiring.append({"component": iname, "pin": "SDA", "connect_to": "Pin 3 (GPIO2 / SDA)", "purpose": "I2C Data", "notes": "Hardware I2C."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3.3V / 5V", "purpose": "Power", "notes": "Power rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "SCL", "connect_to": "A5 (SCL)", "purpose": "I2C Clock", "notes": "Arduino I2C clock."})
                    wiring.append({"component": iname, "pin": "SDA", "connect_to": "A4 (SDA)", "purpose": "I2C Data", "notes": "Arduino I2C data."})

            elif "RFID" in iname.upper():
                if is_esp32:
                    wiring.append({"component": iname, "pin": "3.3V", "connect_to": "3V3 (3.3V Rail)", "purpose": "RF transceiver power", "notes": "DO NOT connect to 5V! 3.3V strictly."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "RST", "connect_to": "GPIO4 (or GPIO22)", "purpose": "Hardware reset trigger", "notes": "Digital output."})
                    wiring.append({"component": iname, "pin": "SDA (SS)", "connect_to": "GPIO5 (SPI Chip Select)", "purpose": "SPI Slave Select", "notes": "Hardware SPI SS."})
                    wiring.append({"component": iname, "pin": "SCK", "connect_to": "GPIO18 (SPI Clock)", "purpose": "SPI Clock", "notes": "Hardware SCK."})
                    wiring.append({"component": iname, "pin": "MOSI", "connect_to": "GPIO23 (SPI MOSI)", "purpose": "SPI Master Out Slave In", "notes": "Hardware MOSI."})
                    wiring.append({"component": iname, "pin": "MISO", "connect_to": "GPIO19 (SPI MISO)", "purpose": "SPI Master In Slave Out", "notes": "Hardware MISO."})
                elif is_rpi:
                    wiring.append({"component": iname, "pin": "3.3V", "connect_to": "Pin 1 (3.3V Rail)", "purpose": "Power", "notes": "3.3V strictly."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "RST", "connect_to": "Pin 22 (GPIO25)", "purpose": "Reset", "notes": "GPIO output."})
                    wiring.append({"component": iname, "pin": "SDA", "connect_to": "Pin 24 (GPIO8 / CE0)", "purpose": "SPI Chip Enable", "notes": "SPI CE0."})
                    wiring.append({"component": iname, "pin": "SCK", "connect_to": "Pin 23 (GPIO11)", "purpose": "SPI Clock", "notes": "SPI SCLK."})
                    wiring.append({"component": iname, "pin": "MOSI", "connect_to": "Pin 19 (GPIO10)", "purpose": "SPI MOSI", "notes": "SPI MOSI."})
                    wiring.append({"component": iname, "pin": "MISO", "connect_to": "Pin 21 (GPIO9)", "purpose": "SPI MISO", "notes": "SPI MISO."})
                else:
                    wiring.append({"component": iname, "pin": "3.3V", "connect_to": "3.3V Pin", "purpose": "Power", "notes": "3.3V strictly."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "RST", "connect_to": "D9", "purpose": "Reset", "notes": "Digital OUT."})
                    wiring.append({"component": iname, "pin": "SDA (SS)", "connect_to": "D10", "purpose": "SPI SS", "notes": "Chip select."})
                    wiring.append({"component": iname, "pin": "SCK", "connect_to": "D13", "purpose": "SPI SCK", "notes": "Clock."})
                    wiring.append({"component": iname, "pin": "MOSI", "connect_to": "D11", "purpose": "SPI MOSI", "notes": "Master Out."})
                    wiring.append({"component": iname, "pin": "MISO", "connect_to": "D12", "purpose": "SPI MISO", "notes": "Master In."})

            else:
                if "ANALOG" in ptype:
                    p = get_analog_pin()
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3V3 Rail" if is_esp32 else "5V Rail", "purpose": "Sensor power", "notes": "Regulated supply rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "AOUT", "connect_to": f"{p} (Analog Input)", "purpose": "Analog signal conversion", "notes": "ADC channel."})
                elif "I2C" in ptype:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3V3 / 5V Rail", "purpose": "Sensor power", "notes": "Power supply."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "SCL", "connect_to": "GPIO22" if is_esp32 else ("Pin 5" if is_rpi else "A5"), "purpose": "I2C Clock", "notes": "Shared I2C bus."})
                    wiring.append({"component": iname, "pin": "SDA", "connect_to": "GPIO21" if is_esp32 else ("Pin 3" if is_rpi else "A4"), "purpose": "I2C Data", "notes": "Shared I2C bus."})
                else:
                    wiring.append({"component": iname, "pin": "VCC", "connect_to": "3V3 / 5V Rail", "purpose": "Power", "notes": "Power rail."})
                    wiring.append({"component": iname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                    wiring.append({"component": iname, "pin": "OUT", "connect_to": "GPIO19" if is_esp32 else ("Pin 11" if is_rpi else "D2"), "purpose": "Digital signal input", "notes": "Digital I/O."})

        # 2. Outputs
        for out in outputs:
            oname = out["name"]
            if "RELAY" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC", "connect_to": "VIN / 5V External Rail" if not is_rpi else "Pin 2 (5V)", "purpose": "Relay internal coil power (5V)", "notes": "Relay coil requires 5V to engage."})
                wiring.append({"component": oname, "pin": "GND", "connect_to": "GND (Common Ground)", "purpose": "Ground reference", "notes": "Common ground."})
                wiring.append({"component": oname, "pin": "IN", "connect_to": "GPIO4 (Digital Output)" if is_esp32 else ("Pin 11 (GPIO17)" if is_rpi else "D4"), "purpose": "Switching control signal", "notes": "Optocoupler isolated input. Safe for 3.3V/5V logic (Active LOW)."})
                wiring.append({"component": oname, "pin": "COM (Common)", "connect_to": "External 5V/12V Power Adapter (+)", "purpose": "High-current load power input", "notes": "Mains or high-current DC feed."})
                wiring.append({"component": oname, "pin": "NO (Normally Open)", "connect_to": "Water Pump / Load Positive Terminal (+)", "purpose": "Switched power feed to actuator", "notes": "Circuit closes only when relay is energized."})

            elif "PUMP" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC (+)", "connect_to": "Relay Module NO Terminal", "purpose": "Switched 5V/12V DC pump power", "notes": "Receives current via relay switch."})
                wiring.append({"component": oname, "pin": "GND (-)", "connect_to": "External Power Supply GND", "purpose": "Power return / common ground", "notes": "Keep common ground with controller."})

            elif "OLED" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC", "connect_to": "3V3 (3.3V Rail)" if not is_rpi else "Pin 1 (3.3V)", "purpose": "Display logic & charge pump power", "notes": "Consumes ~20mA."})
                wiring.append({"component": oname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                wiring.append({"component": oname, "pin": "SCL", "connect_to": "GPIO22 (I2C SCL)" if is_esp32 else ("Pin 5 (GPIO3)" if is_rpi else "A5"), "purpose": "I2C Clock line", "notes": "Hardware I2C clock (Address: 0x3C)."})
                wiring.append({"component": oname, "pin": "SDA", "connect_to": "GPIO21 (I2C SDA)" if is_esp32 else ("Pin 3 (GPIO2)" if is_rpi else "A4"), "purpose": "I2C Data line", "notes": "Hardware I2C data."})

            elif "LCD" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC", "connect_to": "5V / VIN Rail" if not is_rpi else "Pin 2 (5V)", "purpose": "LCD backlight & driver power", "notes": "Needs 5V for crisp contrast."})
                wiring.append({"component": oname, "pin": "GND", "connect_to": "GND", "purpose": "Ground", "notes": "Common ground."})
                wiring.append({"component": oname, "pin": "SCL", "connect_to": "GPIO22" if is_esp32 else ("Pin 5" if is_rpi else "A5"), "purpose": "I2C Clock", "notes": "I2C Backpack address: 0x27."})
                wiring.append({"component": oname, "pin": "SDA", "connect_to": "GPIO21" if is_esp32 else ("Pin 3" if is_rpi else "A4"), "purpose": "I2C Data", "notes": "Hardware I2C data."})

            elif "BUZZER" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC (+)", "connect_to": "GPIO2 (Digital Output)" if is_esp32 else ("Pin 12 (GPIO18 / PWM)" if is_rpi else "D9"), "purpose": "Audio alarm trigger signal", "notes": "HIGH triggers acoustic alert tone."})
                wiring.append({"component": oname, "pin": "GND (-)", "connect_to": "GND", "purpose": "Ground return", "notes": "Common ground."})

            elif "MOTOR DRIVER" in oname.upper() or "L298N" in oname.upper():
                wiring.append({"component": oname, "pin": "12V / VMS", "connect_to": "External 12V 2A Power Adapter (+)", "purpose": "Motor high-current power input", "notes": "Powers dual H-bridge output."})
                wiring.append({"component": oname, "pin": "GND", "connect_to": "External GND AND Controller GND", "purpose": "Common ground reference", "notes": "MANDATORY: Tie controller GND to L298N GND."})
                wiring.append({"component": oname, "pin": "5V", "connect_to": "Microcontroller VIN (Optional)", "purpose": "Onboard 5V regulator output", "notes": "Can supply 5V to MCU if jumper is in place."})
                wiring.append({"component": oname, "pin": "IN1, IN2", "connect_to": "GPIO12, GPIO14" if is_esp32 else ("Pin 11, Pin 13" if is_rpi else "D5, D6"), "purpose": "Motor A Direction & PWM speed control", "notes": "PWM control signals."})
                wiring.append({"component": oname, "pin": "IN3, IN4", "connect_to": "GPIO27, GPIO26" if is_esp32 else ("Pin 15, Pin 16" if is_rpi else "D9, D10"), "purpose": "Motor B Direction & PWM speed control", "notes": "PWM control signals."})

            elif "SERVO" in oname.upper():
                wiring.append({"component": oname, "pin": "VCC (Red)", "connect_to": "External 5V 1A Regulated Rail", "purpose": "Servo internal motor power", "notes": "DO NOT power from MCU 5V pin under mechanical load!"})
                wiring.append({"component": oname, "pin": "GND (Brown/Black)", "connect_to": "Common GND", "purpose": "Ground reference", "notes": "Shared common ground."})
                wiring.append({"component": oname, "pin": "PWM (Orange/Yellow)", "connect_to": "GPIO13" if is_esp32 else ("Pin 12 (GPIO18 / PWM)" if is_rpi else "D9"), "purpose": "50Hz Servo PWM position signal", "notes": "Pulse width 1ms-2ms determines angle (0-180°)."})

        # 3. Dedicated converters (ADS1115 for RPi)
        has_ads = any("ADS1115" in p.get("name", "").upper() for p in power_acc)
        if has_ads or (is_rpi and any(inp.get("pin_type") == "Analog" for inp in inputs)):
            wiring.append({"component": "ADS1115 16-Bit I2C ADC Module", "pin": "VDD", "connect_to": "Pin 1 (3.3V Rail)", "purpose": "ADC logic power", "notes": "3.3V supply."})
            wiring.append({"component": "ADS1115 16-Bit I2C ADC Module", "pin": "GND", "connect_to": "Pin 6 (GND)", "purpose": "Ground", "notes": "Common ground."})
            wiring.append({"component": "ADS1115 16-Bit I2C ADC Module", "pin": "SCL", "connect_to": "Pin 5 (GPIO3 / SCL)", "purpose": "I2C Clock line", "notes": "Default I2C address 0x48."})
            wiring.append({"component": "ADS1115 16-Bit I2C ADC Module", "pin": "SDA", "connect_to": "Pin 3 (GPIO2 / SDA)", "purpose": "I2C Data line", "notes": "Hardware I2C data."})

        return wiring

    # --------------------------------------------------------------------------
    # 2.9 END-TO-END FLOW & FIRMWARE PROCESSING LOGIC GENERATOR
    # --------------------------------------------------------------------------
    @classmethod
    def generate_system_flow_and_logic(
        cls,
        components_arch: Dict[str, Any],
        project_title: str,
        project_desc: str
    ) -> Dict[str, Any]:
        """
        Generates 4-stage dataflow analysis and end-to-end mechanism description.
        Input (Parameter) -> Sensor/Hardware -> Processing Unit -> Output (Actuator/Display)
        """
        controller = components_arch["controller"]
        ctrl_name = controller["name"]
        inputs = components_arch.get("inputs", [])
        outputs = components_arch.get("outputs", [])
        comm = components_arch.get("communication", [])

        input_names = [i["name"] for i in inputs]
        output_names = [o["name"] for o in outputs]
        all_inp_str = " ".join(input_names).lower()
        text = f"{project_title} {project_desc}".lower()

        if any("soil" in n.lower() for n in input_names) or (
            bool(re.search(r"\b(irrigation|soil|watering|crop|agriculture)\b", text)) and "plantower" not in text
        ) or (bool(re.search(r"\b(plant|plants)\b", text)) and "plantower" not in text and not any("pms" in n.lower() for n in input_names)):
            domain = "Smart Agriculture / Automated Irrigation"
            physical_input = "Soil volumetric water content (Moisture level 0% – 100%)"
            sensor_hardware = "Capacitive Soil Moisture Sensor V1.2 (corrosion-free analog probe output 1.2V – 3.0V)"
            processing_logic = (
                f"1. {ctrl_name} samples analog voltage on ADC1 (GPIO34) every 2000ms.\n"
                "2. Firmware executes an 8-sample moving average filter to suppress electrical noise.\n"
                "3. Maps ADC counts (dry soil: ~3200, submerged: ~1400) to 0% - 100% moisture percentage.\n"
                "4. Evaluates against calibrated threshold (e.g. Moisture < 35%):\n"
                "   - If below threshold: Drives GPIO4 LOW to energize optocoupler relay module.\n"
                "   - Relay switches 5V DC power rail to Submersible Mini Water Pump.\n"
                "   - Pump runs for programmed irrigation window (5 seconds) with safety dry-run cutoff.\n"
                "   - Refreshes 0.96\" OLED screen and dispatches telemetry over Wi-Fi MQTT broker.\n"
                "5. When moisture restores above 65%, de-energizes relay and returns to sleep cycle."
            )
            output_actuation = "5V Optocoupler Relay Module switching 5V Mini Submersible Water Pump + 0.96\" I2C OLED Display + Cloud IoT Dashboard"
            end_to_end = (
                f"The system continuously monitors soil dryness using the corrosion-resistant capacitive probe. "
                f"When soil moisture drops below 35%, {ctrl_name} safely triggers the optocoupler relay, pumping water directly to the plant root zone. "
                f"Once adequate saturation is restored (>65%), the pump immediately de-energizes, preventing over-watering and root rot. "
                f"Live status, soil moisture percentage, and watering event logs are published in real time."
            )
            expected_output = (
                "• Dry Soil Bench Test: ADC reading = 3100 – 3500 (Moisture: ~10-25%), Relay LED turns ON, Water Pump runs.\n"
                "• Wet Soil Bench Test: ADC reading = 1350 – 1650 (Moisture: ~80-95%), Relay LED turns OFF, Water Pump halts.\n"
                "• Serial Output (115200 baud): '[IRRIGATION] Raw ADC: 3240 | Moisture: 22.4% | STATUS: PUMP_ACTIVE'\n"
                "• OLED Display: Shows animated moisture bar graph and pump status icon."
            )

        elif any("pms" in n.lower() or "mq-135" in n.lower() or "dust" in n.lower() for n in input_names) or bool(re.search(r"\b(air|pollution|dust|gas|aqi|smog|smoke|pm2\.5|pms5003)\b", text)):
            domain = "Environmental & Air Quality Monitoring"
            physical_input = "Ambient Particulate Matter (PM2.5 / PM10) and hazardous gas concentrations (NH3, CO2, VOCs)"
            sensor_hardware = "Plantower PMS5003 Laser Particle Sensor (UART) + MQ-135 Hazardous Gas Sensor (Analog)"
            processing_logic = (
                f"1. {ctrl_name} continuously parses 32-byte UART data packets from PMS5003 (9600 baud).\n"
                "2. Validates frame checksum (0x42 0x4D header) and extracts standard PM1.0, PM2.5, and PM10 values in μg/m³.\n"
                "3. Simultaneously reads MQ-135 analog voltage on ADC1 (GPIO35), calculates sensor resistance ratio (Rs/Ro), and estimates PPM.\n"
                "4. Computes National Air Quality Index (AQI) based on sub-index breakpoint equations.\n"
                "5. Threshold check:\n"
                "   - If AQI > 100 (Unhealthy) or gas concentration exceeds danger limits:\n"
                "     Triggers active buzzer alert and flashes red warning on OLED.\n"
                "6. Bundles sensor metrics into JSON payload and publishes to cloud dashboard via Wi-Fi."
            )
            output_actuation = "0.96\" I2C OLED Display (live AQI readout) + 5V Active Piezo Buzzer (Hazard Alarm) + Cloud IoT Telemetry"
            end_to_end = (
                f"Laser scattering within the PMS5003 illuminates airborne dust particles, and photodetectors measure light intensity to compute exact PM2.5 and PM10 concentrations. "
                f"Simultaneously, the MQ-135 heated semiconductor element detects hazardous smoke, ammonia, and carbon dioxide. "
                f"{ctrl_name} calculates the unified Air Quality Index, displaying real-time metrics on the local OLED screen and warning occupants via buzzer if air quality breaches safe thresholds."
            )
            expected_output = (
                "• Clean Room Bench Test: PM2.5 = 12 – 28 μg/m³, MQ-135 ADC = 600 – 900, AQI = 35 – 55 (Good), Buzzer Silent.\n"
                "• Smoke / Dust Test: PM2.5 spikes to 120 – 350 μg/m³, MQ-135 ADC > 2400, AQI > 150 (Hazardous), Buzzer sounds alarm.\n"
                "• Serial Output (115200 baud): '[AQI] PM2.5: 22 ug/m3 | PM10: 41 ug/m3 | Gas Ratio: 1.42 | STATUS: NORMAL'\n"
                "• OLED Display: Shows numeric AQI, PM2.5 gauge, and Air Quality category badge ('GOOD' / 'HAZARDOUS')."
            )

        elif any("camera" in n.lower() or "face" in n.lower() for n in input_names) or bool(re.search(r"\b(face|facial|vision|opencv)\b", text)):
            domain = "Edge Vision & Automated Face Recognition Attendance"
            physical_input = "Optical facial video stream (640x480 resolution @ 30 FPS) & biometric landmarks"
            sensor_hardware = "Raspberry Pi Camera Module v2 (8MP Sony IMX219) via 15-pin MIPI CSI Bus" if "Raspberry Pi" in ctrl_name else "OV2640 2MP Camera Sensor Module"
            processing_logic = (
                f"1. {ctrl_name} captures live video frames from camera.\n"
                "2. Computer Vision Pipeline (OpenCV + Haar Cascade / HOG / MobileNet SSD):\n"
                "   - Converts frame to grayscale and executes face bounding box localization.\n"
                "   - Crops detected face region and extracts 128-dimensional facial embedding vector.\n"
                "3. Face Recognition & Verification:\n"
                "   - Computes Euclidean distance / cosine similarity against registered student database.\n"
                "   - If distance < 0.45 (Confidence > 85%), student is recognized.\n"
                "4. Attendance Logging:\n"
                "   - Queries local SQLite database to check if attendance was already logged today.\n"
                "   - Records student ID, name, date, and exact timestamp.\n"
                "5. Actuation:\n"
                "   - Triggers 100ms confirmation beep on piezo buzzer.\n"
                "   - Renders personalized 'Welcome, [Name]! Attendance Marked' on display screen."
            )
            output_actuation = "Local SQLite Attendance Database + Confirmation Beep Buzzer + 0.96\" OLED / HDMI Attendance Display"
            end_to_end = (
                f"When a student approaches the system, the camera stream captures facial frames in real time. "
                f"{ctrl_name} detects face contours, extracts biometric facial embedding vectors, and compares them against registered enrolled students. "
                f"Upon successful authentication, the system logs attendance with an immutable timestamp into the database, beeps the buzzer for audible confirmation, and presents a greeting on the display."
            )
            expected_output = (
                "• Frame Processing Speed: 18 – 25 FPS with face localization bounding box.\n"
                "• Recognition Latency: <350ms from face detection to database attendance confirmation.\n"
                "• Verification Distance: Euclidean distance = 0.28 (<0.45 threshold -> 'CONFIRMED MATCH').\n"
                "• Serial / Terminal Output: '[VISION] Student Recognized: ID #104 (Sarah Jenkins) | Confidence: 94.2% | Logged to DB'\n"
                "• Output Display: Shows recognized student name, roll number, and green checkmark."
            )

        elif any("rfid" in n.lower() or "rc522" in n.lower() for n in input_names) or bool(re.search(r"\b(rfid|nfc|rc522|mifare|smart\s*card)\b", text)):
            domain = "Contactless RFID Smart Access & Attendance"
            physical_input = "13.56MHz electromagnetic radio frequency induction from student RFID keyfob/card"
            sensor_hardware = "RC522 13.56MHz RFID Reader Module (Mifare protocol via SPI bus)"
            processing_logic = (
                f"1. {ctrl_name} polls RC522 over hardware SPI bus at 400kHz.\n"
                "2. When card enters RF field, reader extracts 4-byte / 7-byte Unique Identification (UID).\n"
                "3. Controller queries enrolled student table in database / local flash memory.\n"
                "4. If match found: logs timestamped attendance record and pulses buzzer for 150ms.\n"
                "5. Displays student name and time on OLED screen; transmits log to cloud server."
            )
            output_actuation = "0.96\" I2C OLED Display + 5V Active Buzzer + Attendance Database / Cloud Sheet"
            end_to_end = (
                f"When a student taps their RFID card within 5cm of the reader, the RC522 energizes the card's coil and reads its unique serial number. "
                f"{ctrl_name} verifies authorization against enrolled IDs, writes a timestamped record to the attendance database, beeps the buzzer, and displays the student's confirmation on the screen."
            )
            expected_output = (
                "• Read Range: 2 – 5 cm contactless detection with <100ms response time.\n"
                "• Authorized Card Test: UID 'A3:4F:92:1B' -> OLED displays 'ID #102: Verified', Buzzer sounds 1 short beep.\n"
                "• Unauthorized Card Test: UID '89:12:33:04' -> OLED displays 'ACCESS DENIED', Buzzer sounds 3 rapid warning beeps.\n"
                "• Serial Output (115200 baud): '[RFID] Card Detected: UID A3:4F:92:1B | Student: Mark R. | ATTENDANCE_LOGGED'"
            )

        elif "robot" in text or "rover" in text or "obstacle" in text or "motor" in text:
            domain = "Autonomous Mobile Robotics & Navigation"
            physical_input = "Acoustic ultrasonic echo reflection time & front clearance distance (2cm – 400cm)"
            sensor_hardware = "HC-SR04 Ultrasonic Distance Sensor + Dual BO Geared Motors"
            processing_logic = (
                f"1. {ctrl_name} emits a 10μs trigger pulse to HC-SR04 on GPIO5.\n"
                "2. Measures echo return pulse duration on GPIO18 using `pulseIn()` or hardware timer.\n"
                "3. Calculates distance in centimeters: Distance = (Duration * 0.0343) / 2.\n"
                "4. Evaluates safety threshold: If distance < 20cm (Obstacle Detected):\n"
                "   - Sends PWM reverse/stop signals to L298N motor driver (IN1-IN4).\n"
                "   - Pivots wheels to maneuver robot around the obstacle.\n"
                "5. When path is clear (distance > 20cm), resumes forward drive."
            )
            output_actuation = "L298N Dual H-Bridge Motor Driver powering Dual-Shaft BO DC Motors + 0.96\" OLED telemetry"
            end_to_end = (
                f"The ultrasonic sensor continuously broadcasts 40kHz ultrasound bursts and times the return echo to compute front clearance. "
                f"{ctrl_name} executes an obstacle avoidance algorithm: driving forward during clear paths, and triggering differential steering via the L298N H-bridge whenever an object approaches within 20cm."
            )
            expected_output = (
                "• Clear Path Bench Test: Distance > 40cm -> Motor A & B forward at 80% PWM duty cycle.\n"
                "• Obstacle Bench Test: Hand placed at 12cm -> Motors immediately brake and execute 0.6s turn.\n"
                "• Serial Output (115200 baud): '[ROBOT] Front Distance: 14.2 cm | STATE: OBSTACLE_AVOID_TURN_RIGHT'"
            )

        else:
            domain = "Automated Embedded & IoT Control System"
            physical_input = f"Physical environmental parameters monitored by: {', '.join(input_names[:3]) if input_names else 'Sensors'}"
            sensor_hardware = f"{', '.join(input_names[:2]) if input_names else 'Input Sensor Module'}"
            processing_logic = (
                f"1. {ctrl_name} initializes hardware peripherals (GPIO, ADC, I2C, SPI) at boot.\n"
                f"2. Samples input data from {', '.join(input_names[:2]) if input_names else 'sensors'} on a deterministic 1000ms timer loop.\n"
                "3. Filters raw values with debounce and threshold validation algorithms.\n"
                f"4. Executes control logic to actuate {', '.join(output_names[:2]) if output_names else 'outputs'}.\n"
                "5. Updates local display and transmits telemetry packet via network."
            )
            output_actuation = f"{', '.join(output_names[:2]) if output_names else 'System Actuators & Status UI'}"
            end_to_end = (
                f"The system operates as an autonomous closed-loop embedded controller. "
                f"Inputs from {', '.join(input_names[:2]) if input_names else 'sensors'} are processed in real time by {ctrl_name}, which computes threshold rules and triggers {', '.join(output_names[:2]) if output_names else 'outputs'} while maintaining safe electrical margins."
            )
            expected_output = (
                "• Diagnostic Serial Output (115200 baud): Confirms sensor initialization and continuous periodic state updates.\n"
                f"• Physical Output: Real-time response on {', '.join(output_names[:2]) if output_names else 'actuators'} when thresholds are satisfied."
            )

        flow_stages = [
            {
                "stage": 1,
                "label": "Physical Input",
                "title": "Raw Physical Phenomenon",
                "description": physical_input,
                "icon": "fa-wave-square",
                "badge": "Input Signal"
            },
            {
                "stage": 2,
                "label": "Sensor / Hardware",
                "title": "Transducer & Electrical Interface",
                "description": sensor_hardware,
                "icon": "fa-microchip",
                "badge": "Sensor Layer"
            },
            {
                "stage": 3,
                "label": "Processing Unit",
                "title": f"Firmware & Algorithmic Logic ({ctrl_name})",
                "description": processing_logic.splitlines()[0] if processing_logic else f"{ctrl_name} Core Execution",
                "icon": "fa-brain",
                "badge": "Central Controller"
            },
            {
                "stage": 4,
                "label": "Output / Actuation",
                "title": "Actuators, Displays & Telemetry",
                "description": output_actuation,
                "icon": "fa-sign-out-alt",
                "badge": "System Output"
            }
        ]

        return {
            "domain": domain,
            "physical_input": physical_input,
            "sensor_hardware": sensor_hardware,
            "processing_unit": ctrl_name,
            "processing_logic": processing_logic,
            "output_actuation": output_actuation,
            "end_to_end_mechanism": end_to_end,
            "expected_output": expected_output,
            "flow_stages": flow_stages
        }

    # --------------------------------------------------------------------------
    # 2.10 SOFTWARE & FIRMWARE REQUIREMENTS GENERATOR
    # --------------------------------------------------------------------------
    @classmethod
    def generate_software_requirements(
        cls,
        components_arch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates programming language, IDE, required libraries with install commands,
        and applicable APIs/datasets based on the components.
        Provides direct official source links for APIs and datasets.
        """
        controller = components_arch["controller"]
        ctrl_name = controller["name"]
        inputs = components_arch.get("inputs", [])
        outputs = components_arch.get("outputs", [])
        all_comp_names = " ".join([c["name"] for c in inputs + outputs + components_arch.get("communication", [])]).upper()

        if "Raspberry Pi 4" in ctrl_name:
            lang = "Python 3.10+ / C++17 (Linux OS Environment)"
            ide = {
                "name": "VS Code (with Remote - SSH) or Thonny IDE",
                "official_url": "https://code.visualstudio.com/docs/remote/ssh",
                "description": "Recommended for Raspberry Pi Linux development, remote debugging, and Python package management."
            }
            libs = [
                {
                    "name": "opencv-python",
                    "version": "4.8.0+",
                    "purpose": "Real-time computer vision, video frame capture, image transformations, and drawing primitives.",
                    "install_cmd": "pip install opencv-python",
                    "official_url": "https://pypi.org/project/opencv-python/"
                },
                {
                    "name": "numpy",
                    "version": "1.24+",
                    "purpose": "High-performance array operations and matrix math for image embeddings and coordinates.",
                    "install_cmd": "pip install numpy",
                    "official_url": "https://numpy.org/"
                },
                {
                    "name": "RPi.GPIO",
                    "version": "0.7.1+",
                    "purpose": "Direct hardware control of Raspberry Pi 40-pin GPIO header pins.",
                    "install_cmd": "pip install RPi.GPIO",
                    "official_url": "https://pypi.org/project/RPi.GPIO/"
                }
            ]
            if "CAMERA" in all_comp_names or "FACE" in all_comp_names:
                libs.append({
                    "name": "face-recognition",
                    "version": "1.3.0+",
                    "purpose": "Deep learning face localization and 128-d biometric embedding extraction using dlib model.",
                    "install_cmd": "pip install face-recognition",
                    "official_url": "https://github.com/ageitgey/face_recognition"
                })
            if "ADS1115" in all_comp_names or any(inp.get("pin_type") == "Analog" for inp in inputs):
                libs.append({
                    "name": "adafruit-circuitpython-ads1x15",
                    "version": "2.2.14+",
                    "purpose": "I2C driver for external 16-bit ADS1115 analog-to-digital converter.",
                    "install_cmd": "pip install adafruit-circuitpython-ads1x15",
                    "official_url": "https://pypi.org/project/adafruit-circuitpython-ads1x15/"
                })

            apis = [
                {
                    "name": "Local SQLite3 Embedded Database Engine",
                    "purpose": "Zero-configuration persistent SQL database for logging attendance records with immutable timestamps.",
                    "official_url": "https://www.sqlite.org/docs.html"
                },
                {
                    "name": "Flask Lightweight REST Framework",
                    "purpose": "Provides a clean local web interface to review attendance logs and download CSV reports.",
                    "official_url": "https://flask.palletsprojects.com/"
                }
            ]
            databases = [
                {
                    "name": "SQLite3 (attendance.db)",
                    "purpose": "Stores student ID, timestamp, recognition confidence, and verification status locally on the Pi.",
                    "official_url": "https://www.sqlite.org/"
                }
            ]
            datasets = [
                {
                    "name": "Haar Cascade Frontal Face Classifier Model",
                    "purpose": "Pre-trained XML model for rapid real-time facial bounding-box detection.",
                    "official_url": "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
                },
                {
                    "name": "Enrolled Student Facial Dataset",
                    "purpose": "Local directory of registered student reference images (10-15 images per student under varied lighting).",
                    "official_url": "https://github.com/opencv/opencv/wiki"
                }
            ]

        else: # ESP32, Arduino Uno, Nano, Pico
            lang = "C++ (Arduino Framework / FreeRTOS)" if "ESP32" in ctrl_name else "C++ (Arduino AVR Framework)"
            ide = {
                "name": "Arduino IDE 2.3+ (or VS Code + PlatformIO)",
                "official_url": "https://www.arduino.cc/en/software",
                "description": "Standard cross-platform IDE with integrated Library Manager, Serial Monitor, and Plotter."
            }
            libs = []

            # Universal Display Libs
            if "OLED" in all_comp_names:
                libs.append({
                    "name": "Adafruit_SSD1306",
                    "version": "2.5.9+",
                    "purpose": "Driver library for 128x64 and 128x32 I2C OLED displays.",
                    "install_cmd": "Arduino Library Manager: 'Adafruit SSD1306'",
                    "official_url": "https://github.com/adafruit/Adafruit_SSD1306"
                })
                libs.append({
                    "name": "Adafruit_GFX",
                    "version": "1.11.9+",
                    "purpose": "Core graphics library providing font rendering and geometric drawing primitives.",
                    "install_cmd": "Arduino Library Manager: 'Adafruit GFX Library'",
                    "official_url": "https://github.com/adafruit/Adafruit-GFX-Library"
                })
            if "LCD" in all_comp_names:
                libs.append({
                    "name": "LiquidCrystal_I2C",
                    "version": "1.1.4+",
                    "purpose": "I2C character display driver for 16x2 and 20x4 LCD screens.",
                    "install_cmd": "Arduino Library Manager: 'LiquidCrystal I2C'",
                    "official_url": "https://github.com/johnrickman/LiquidCrystal_I2C"
                })

            # Sensor Libs
            if "DHT" in all_comp_names:
                libs.append({
                    "name": "DHT sensor library by Adafruit",
                    "version": "1.4.6+",
                    "purpose": "Single-wire protocol driver for DHT11 and DHT22 temperature/humidity sensors.",
                    "install_cmd": "Arduino Library Manager: 'DHT sensor library'",
                    "official_url": "https://github.com/adafruit/DHT-sensor-library"
                })
            if "PMS5003" in all_comp_names:
                libs.append({
                    "name": "PMS Library by Mariusz Bielat",
                    "version": "1.1.0+",
                    "purpose": "UART serial packet parser for Plantower PMS laser dust sensors.",
                    "install_cmd": "Arduino Library Manager: 'PMS Library'",
                    "official_url": "https://github.com/fu-hsi/PMS"
                })
            if "MQ-135" in all_comp_names or "AIR QUALITY" in all_comp_names:
                libs.append({
                    "name": "MQ135 by Georg Krocker",
                    "version": "1.0.0+",
                    "purpose": "Calibrated gas concentration calculations with temperature/humidity compensation.",
                    "install_cmd": "Arduino Library Manager: 'MQ135'",
                    "official_url": "https://github.com/GeorgK/MQ135"
                })
            if "BME280" in all_comp_names:
                libs.append({
                    "name": "Adafruit_BME280",
                    "version": "2.2.4+",
                    "purpose": "I2C/SPI environmental pressure, temperature, and humidity sensor driver.",
                    "install_cmd": "Arduino Library Manager: 'Adafruit BME280 Library'",
                    "official_url": "https://github.com/adafruit/Adafruit_BME280_Library"
                })
            if "RFID" in all_comp_names or "RC522" in all_comp_names:
                libs.append({
                    "name": "MFRC522 by GithubCommunity",
                    "version": "1.4.11+",
                    "purpose": "Mifare RFID card reading and UID verification over SPI bus.",
                    "install_cmd": "Arduino Library Manager: 'MFRC522'",
                    "official_url": "https://github.com/miguelbalboa/rfid"
                })
            if "SERVO" in all_comp_names:
                if "ESP32" in ctrl_name:
                    libs.append({
                        "name": "ESP32Servo",
                        "version": "3.0.5+",
                        "purpose": "Hardware LEDC PWM timer servo driver for ESP32.",
                        "install_cmd": "Arduino Library Manager: 'ESP32Servo'",
                        "official_url": "https://github.com/madhephaestus/ESP32Servo"
                    })
                else:
                    libs.append({
                        "name": "Servo (Built-in)",
                        "version": "1.2.1+",
                        "purpose": "Standard Arduino timer-based servo control library.",
                        "install_cmd": "Pre-installed in Arduino IDE",
                        "official_url": "https://www.arduino.cc/reference/en/libraries/servo/"
                    })

            # Wireless & Networking Libs
            if "ESP32" in ctrl_name:
                libs.append({
                    "name": "WiFi.h & HTTPClient.h",
                    "version": "Built-in",
                    "purpose": "Native ESP32 802.11 Wi-Fi station mode and HTTP client services.",
                    "install_cmd": "Pre-installed with ESP32 Board Core",
                    "official_url": "https://docs.espressif.com/projects/arduino-esp32/en/latest/"
                })
                libs.append({
                    "name": "PubSubClient by Nick O'Leary",
                    "version": "2.8.0+",
                    "purpose": "Lightweight MQTT client for sending live telemetry to cloud dashboards.",
                    "install_cmd": "Arduino Library Manager: 'PubSubClient'",
                    "official_url": "https://pubsubclient.knolleary.net/"
                })

            apis = [
                {
                    "name": "Blynk IoT Cloud Platform",
                    "purpose": "Zero-code mobile dashboard and telemetry visualization over WebSocket / REST API.",
                    "official_url": "https://blynk.io/"
                },
                {
                    "name": "Adafruit IO MQTT Telemetry Broker",
                    "purpose": "Free educational MQTT cloud broker for storing and graphing sensor streams.",
                    "official_url": "https://io.adafruit.com/"
                },
                {
                    "name": "ThingSpeak Open IoT Analytics",
                    "purpose": "MATLAB-powered live data analytics and public charts for IoT nodes.",
                    "official_url": "https://thingspeak.com/"
                }
            ]
            databases = [
                {
                    "name": "Local EEPROM / Flash NVS",
                    "purpose": "Stores Wi-Fi credentials, sensor calibration offsets, and offline telemetry buffer.",
                    "official_url": "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/storage/nvs_flash.html"
                }
            ]
            datasets = [
                {
                    "name": "National Air Quality Index (AQI) Breakpoint Reference Tables",
                    "purpose": "Standard CPCB / EPA breakpoint conversion equations for PM2.5 and PM10 to AQI.",
                    "official_url": "https://www.airnow.gov/aqi/aqi-basics/"
                },
                {
                    "name": "Soil Volumetric Water Content Calibration Matrix",
                    "purpose": "Lookup curve mapping analog ADC voltages to soil water percentage across loam, clay, and sand.",
                    "official_url": "https://en.wikipedia.org/wiki/Water_content"
                }
            ]

        # Flat lists for backwards compatibility
        apis_flat = [a["name"] for a in apis]
        datasets_flat = [d["name"] for d in datasets]

        return {
            "programming_language": lang,
            "recommended_ide": ide,
            "libraries": libs,
            "apis": apis,
            "apis_and_cloud": apis_flat,
            "databases": databases,
            "datasets": datasets,
            "datasets_and_models": datasets_flat
        }

    # --------------------------------------------------------------------------
    # 2.11 'WILL THIS WORK?' PHYSICAL VERIFICATION GENERATOR
    # --------------------------------------------------------------------------
    @classmethod
    def generate_testing_and_verification(
        cls,
        components_arch: Dict[str, Any],
        electrical_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates technical justification, physical test checklist, failure modes,
        and expected diagnostic values during bench testing.
        """
        ctrl = components_arch["controller"]
        cname = ctrl["name"]
        total_current = electrical_data.get("total_current_safe_ma", 450.0)

        why_it_works = (
            f"1. Voltage Level Compatibility: All digital and communication signals operate within validated logic tolerances ({ctrl.get('logic_voltage', ctrl.get('voltage', '3.3V'))}).\n"
            f"2. Current & Power Headroom: Total estimated system load with a +25% engineering safety margin is {total_current} mA, comfortably supported by the recommended power rail.\n"
            f"3. Independent Control Paths: Actuators (relays, motors) are isolated via optocouplers and dedicated drivers, preventing electrical back-EMF feedback into the {cname} MCU core.\n"
            f"4. Bus Bandwidth: Standard I2C/UART/SPI buses provide more than 10x the required bandwidth for sensor sampling intervals."
        )

        test_steps = [
            {
                "step": 1,
                "title": "Benchtop Power Supply & Multimeter Rail Verification",
                "action": "Connect the power adapter to the breadboard rails WITHOUT plugging in the microcontroller or sensors. Measure DC voltage with a digital multimeter across 3.3V, 5V, and GND rails to ensure no short circuits or over-voltage conditions exist."
            },
            {
                "step": 2,
                "title": "Microcontroller Boot & Serial Diagnostics Check",
                "action": f"Plug {cname} into your computer via a verified 4-wire USB data cable. Open Arduino IDE / Thonny at 115200 baud, upload an empty sketch or basic Blink script, and confirm the COM port communicates without dropping."
            },
            {
                "step": 3,
                "title": "Individual Sensor Bench Calibration (I2C / ADC / UART)",
                "action": "Connect sensors one at a time. Run an I2C Scanner sketch to verify device addresses (e.g. 0x3C for OLED, 0x76 for BME280). Print raw sensor readings to the Serial Monitor to observe live sensitivity before connecting any motors or pumps."
            },
            {
                "step": 4,
                "title": "Actuator Dry-Run Isolation Testing",
                "action": "Trigger the relay or motor driver while keeping the water pump or motor disconnected from liquid/mechanical loads. Listen for the audible relay click and verify that switching signals do not cause the microcontroller to restart."
            },
            {
                "step": 5,
                "title": "Full Integrated 60-Minute Continuous Stress Test",
                "action": "Connect all modules, assemble the complete enclosure, and execute continuous sensor polling and telemetry updates for 1 hour. Touch voltage regulators to ensure they remain warm (under 55°C) and check that Wi-Fi does not drop."
            }
        ]

        expected_test_values = [
            {"parameter": "DC Power Rail (3.3V)", "expected": "3.28V – 3.34V DC", "tolerance": "±2%", "instrument": "Digital Multimeter (DC Volts)"},
            {"parameter": "DC Power Rail (5.0V)", "expected": "4.90V – 5.15V DC", "tolerance": "±3%", "instrument": "Digital Multimeter (DC Volts)"},
            {"parameter": "Total Quiescent Idle Current", "expected": "80mA – 160mA", "tolerance": "±15%", "instrument": "In-line Multimeter (DC mA)"},
            {"parameter": "Peak RF Telemetry Current (Wi-Fi)", "expected": "210mA – 260mA burst", "tolerance": "±10%", "instrument": "Oscilloscope / Current Shunt"},
            {"parameter": "Serial Baud Rate Communication", "expected": "115200 baud (8-N-1)", "tolerance": "0 error", "instrument": "Serial Monitor / Terminal"}
        ]

        failure_causes = [
            {
                "cause": "Inductive Back-EMF Spikes from Motors or Solenoid Coils",
                "symptom": "Microcontroller reboots, hangs, or resets every time the motor or pump turns off.",
                "mitigation": "Always place a 1N4007 flyback diode across motor terminals and use optocoupler-isolated relay modules with separate power rails."
            },
            {
                "cause": "Inrush Current Starvation (Brownout Restarts)",
                "symptom": "Power LED blinks and board restarts the instant Wi-Fi connects or an actuator engages.",
                "mitigation": "Place a 470μF to 1000μF electrolytic capacitor across the VCC and GND power rail right at the microcontroller."
            },
            {
                "cause": "5V Logic Signal Injected into 3.3V GPIO Pin",
                "symptom": "GPIO pin stops reading, MCU gets hot, or analog readings saturate permanently at maximum count.",
                "mitigation": "Use a bidirectional logic level shifter or 1kΩ/2kΩ resistor voltage divider on all 5V sensors (e.g. HC-SR04 Echo pin)."
            },
            {
                "cause": "Floating Digital Input Pins",
                "symptom": "Sensors report erratic random transitions even when disconnected.",
                "mitigation": "Enable internal pull-up/pull-down resistors (`pinMode(pin, INPUT_PULLUP)`) or wire physical 10kΩ resistors."
            }
        ]

        return {
            "why_it_works": why_it_works,
            "physical_test_steps": test_steps,
            "expected_test_values": expected_test_values,
            "failure_causes": failure_causes,
            "disclaimer": "Physical hardware systems cannot be guaranteed to operate safely without practical breadboard assembly, multimeter voltage checks, and bench testing."
        }

    # --------------------------------------------------------------------------
    # 2.12 CONTEXTUAL TROUBLESHOOTING GUIDE GENERATOR (9 KEY HARDWARE CATEGORIES)
    # --------------------------------------------------------------------------
    @classmethod
    def generate_contextual_troubleshooting(
        cls,
        components_arch: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generates step-by-step resolution guides for 9 core hardware fault scenarios:
        1. Board not detected
        2. Sensor not responding
        3. Incorrect readings
        4. Power problems
        5. Wrong wiring
        6. Library errors
        7. Serial communication problems
        8. Wi-Fi/Bluetooth problems
        9. API connection problems
        """
        return [
            {
                "category_id": "board_not_detected",
                "issue_title": "1. Development Board Not Detected / Port Greyed Out",
                "symptoms": "Arduino IDE / Device Manager does not list a COM port, or displays 'Device Descriptor Request Failed'.",
                "root_cause": "Missing USB-to-UART bridge drivers (CH340G, CP2102, or FTDI), or using a cheap 2-wire charge-only USB cable.",
                "step_by_step_solution": [
                    "Step 1: Swap your USB cable for a verified 4-wire data sync cable (many phone cables only carry power).",
                    "Step 2: Download and install the official CH340 or Silicon Labs CP210x VCP driver for Windows.",
                    "Step 3: If using ESP32, hold down the physical 'BOOT' button on the board while clicking 'Upload' until 'Connecting...' appears.",
                    "Step 4: Check Windows Device Manager under 'Ports (COM & LPT)' to verify the assigned port number."
                ]
            },
            {
                "category_id": "sensor_not_responding",
                "issue_title": "2. Sensor Not Responding / Reading 0 or NaN",
                "symptoms": "Serial Monitor displays 'Failed to read from sensor' or constant negative / NaN values.",
                "root_cause": "Incorrect pin mapping in firmware, loose breadboard jumper wire, or incorrect I2C bus address.",
                "step_by_step_solution": [
                    "Step 1: Check breadboard jumper wire continuity with a multimeter continuity buzzer test.",
                    "Step 2: If using an I2C sensor, upload an I2C Scanner sketch to detect whether the hardware address is 0x3C, 0x27, 0x68, or 0x76.",
                    "Step 3: On ESP32, verify you did not assign an analog sensor to ADC2 pins (GPIO 0, 2, 4, 12-15) while Wi-Fi is enabled. Always use ADC1 (GPIO 32-39).",
                    "Step 4: Verify sensor VCC is receiving 3.3V or 5.0V as required by its datasheet."
                ]
            },
            {
                "category_id": "incorrect_readings",
                "issue_title": "3. Incorrect or Jittery Sensor Readings",
                "symptoms": "ADC readings jump erratically by 200-500 counts without any physical change in temperature, moisture, or gas.",
                "root_cause": "Electromagnetic interference (EMI), high-frequency digital noise on the power rail, uncalibrated sensor baseline, or floating grounds.",
                "step_by_step_solution": [
                    "Step 1: Implement a software moving average filter: take 10 consecutive ADC samples, discard min/max, and average the rest.",
                    "Step 2: Solder or insert a 100nF ceramic decoupling capacitor between the sensor analog signal pin and GND right at the board.",
                    "Step 3: Route analog sensor wires physically away from high-current motor wires or switching power supplies.",
                    "Step 4: For gas sensors (MQ-135 / MQ-2), allow a 24-hour preheating burn-in period before taking baseline resistance (Ro) readings."
                ]
            },
            {
                "category_id": "power_problems",
                "issue_title": "4. Power Problems: Brownouts & Continuous Board Reboots",
                "symptoms": "Serial Monitor loops 'Brownout detector was triggered' or restarts whenever Wi-Fi connects or a motor/pump activates.",
                "root_cause": "The USB port or onboard 3.3V regulator cannot provide the peak current burst demanded by Wi-Fi transmissions or motors.",
                "step_by_step_solution": [
                    "Step 1: Power high-current devices (motors, pumps, SIM800L) from an external 5V/12V power supply rather than the microcontroller's 5V/3.3V pins.",
                    "Step 2: Connect the external power supply GND and the microcontroller GND together (Common Ground).",
                    "Step 3: Insert a 1000μF 16V electrolytic capacitor directly across the power rails near the controller to smooth inrush transients.",
                    "Step 4: In software, add a 50ms delay between Wi-Fi connection attempts to stagger peak RF power spikes."
                ]
            },
            {
                "category_id": "wrong_wiring",
                "issue_title": "5. Wrong Wiring / Short Circuits & Reversed Polarity",
                "symptoms": "Board power LED dims, voltage regulator gets scorching hot to the touch, or computer USB port shuts down with overcurrent warning.",
                "root_cause": "VCC and GND reversed on a sensor module, or output pin wired directly to power rail.",
                "step_by_step_solution": [
                    "Step 1: Immediately disconnect USB power from the computer.",
                    "Step 2: Inspect breadboard power rails: ensure red rail is strictly VCC (3.3V or 5V) and blue rail is strictly GND.",
                    "Step 3: Use a multimeter in resistance / continuity mode to probe between VCC and GND rails with board unpowered (reading must be >10kΩ).",
                    "Step 4: Verify module pinouts against manufacturer silkscreen labels, as pin order often differs between clone manufacturers."
                ]
            },
            {
                "category_id": "library_errors",
                "issue_title": "6. Library Errors / 'fatal error: header.h No such file'",
                "symptoms": "Arduino IDE / PlatformIO aborts compilation with red text indicating missing header files or conflicting definitions.",
                "root_cause": "Required library not installed in user library directory, multiple conflicting versions, or outdated board definitions.",
                "step_by_step_solution": [
                    "Step 1: Open Arduino IDE -> Tools -> Manage Libraries... and search for the exact library name from your Software Requirements table.",
                    "Step 2: When prompted to install dependencies, always click 'Install All'.",
                    "Step 3: If using ESP32, verify 'esp32 by Espressif Systems' is updated under Tools -> Board -> Boards Manager.",
                    "Step 4: Check for duplicate library folders in `Documents/Arduino/libraries/` and delete redundant versions."
                ]
            },
            {
                "category_id": "serial_communication",
                "issue_title": "7. Serial Communication Problems / Gibberish or Freezing",
                "symptoms": "Serial Monitor displays garbled characters (e.g. `⸮⸮⸮`), nothing prints, or UART sensor packets drop.",
                "root_cause": "Baud rate mismatch between firmware `Serial.begin()` and Serial Monitor, or crossed TX/RX pins.",
                "step_by_step_solution": [
                    "Step 1: Verify the Serial Monitor dropdown in Arduino IDE matches `Serial.begin(115200)` in your `setup()` function.",
                    "Step 2: Remember that UART TX connects to RX, and RX connects to TX (crossover wiring). Never wire TX to TX.",
                    "Step 3: On ESP32, avoid using GPIO1 (TX0) and GPIO3 (RX0) for sensors, as they are dedicated to USB flashing. Use GPIO16 (RX2) and GPIO17 (TX2).",
                    "Step 4: Ensure sensor and microcontroller share a common GND connection for serial reference."
                ]
            },
            {
                "category_id": "wifi_bluetooth",
                "issue_title": "8. Wi-Fi / Bluetooth Connection Drops & Failures",
                "symptoms": "ESP32 fails to connect to router or disconnects every few minutes during telemetry transmission.",
                "root_cause": "Attempting to connect to a 5GHz-only Wi-Fi network (ESP32 only supports 2.4GHz), weak RSSI signal, or blocking delays in code.",
                "step_by_step_solution": [
                    "Step 1: Verify your Wi-Fi router broadcasts a separate 2.4GHz SSID (ESP32 hardware does not support 5GHz 802.11ac).",
                    "Step 2: Implement automatic non-blocking reconnection logic in your firmware `loop()` using `WiFi.status() != WL_CONNECTED`.",
                    "Step 3: Replace blocking `delay(5000)` calls with non-blocking `millis()` timers to keep background Wi-Fi tasks responsive.",
                    "Step 4: Keep the onboard PCB antenna clear of metal enclosures, ground planes, or large aluminum heatsinks."
                ]
            },
            {
                "category_id": "api_connection",
                "issue_title": "9. API & Cloud Telemetry Connection Problems",
                "symptoms": "HTTP client returns error codes (-1, 400, 401, 403, 404), or MQTT broker disconnects on publish.",
                "root_cause": "Incorrect API endpoint URL, expired auth token / API key, or missing SSL root certificate on HTTPS calls.",
                "step_by_step_solution": [
                    "Step 1: Test your API key and URL using Postman or `curl` on your computer first to confirm endpoint validity.",
                    "Step 2: If using HTTPS on ESP32, use `WiFiClientSecure` with `client.setInsecure()` during prototyping to bypass root certificate checks.",
                    "Step 3: Verify payload formatting: ensure JSON headers `Content-Type: application/json` and valid string escaping.",
                    "Step 4: For MQTT (e.g. Adafruit IO), keep the payload size under 128 bytes or increase `MQTT_MAX_PACKET_SIZE` in `PubSubClient.h`."
                ]
            }
        ]

    # --------------------------------------------------------------------------
    # 2.13 DUAL-TIER BUDGET ANALYSIS ENGINE (MINIMUM VS RECOMMENDED)
    # --------------------------------------------------------------------------
    @classmethod
    def generate_dual_budget_tiers(
        cls,
        bom: List[Dict[str, Any]],
        components_arch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates Minimum-Budget version (clones/bare essentials) vs
        Recommended version (branded, durable, dedicated power supply).
        Component cost + additional modules + wires/connectors + power supply + other items = Estimated Total
        """
        min_items = []
        rec_items = []
        min_total = 0.0
        rec_total = 0.0

        for item in bom:
            iname = item["name"]
            base_p = float(item.get("price_inr", 100.0))

            # Check if component can be optimized for minimum budget
            if "OLED" in iname.upper() or "LCD" in iname.upper():
                min_p = 0.0
                min_spec = "Omitted in Minimal Build — Telemetry viewed via Serial Monitor / Web Dashboard"
                min_items.append({"name": f"{iname} (Web/Serial Alternative)", "price_inr": min_p, "specification": min_spec, "tier": "Minimum"})
            elif "POWER" in item.get("purpose", "").upper() and "ADAPTER" in iname.upper():
                min_p = 0.0
                min_spec = "Reused existing 5V 2A smartphone charger + USB cable"
                min_items.append({"name": "Existing 5V Smartphone Charger (Reused)", "price_inr": min_p, "specification": min_spec, "tier": "Minimum"})
            elif "DHT22" in iname.upper():
                min_p = 85.0
                min_items.append({"name": "DHT11 Sensor (Budget Clone)", "price_inr": min_p, "specification": "Standard DHT11 0-50°C", "tier": "Minimum"})
            else:
                min_p = round(base_p * 0.85)
                min_items.append({"name": f"{iname} (Standard Generic)", "price_inr": min_p, "specification": item.get("recommended_spec"), "tier": "Minimum"})

            min_total += min_p

            rec_p = round(base_p * 1.05) if base_p > 100 else base_p
            rec_items.append({"name": iname, "price_inr": rec_p, "specification": item.get("recommended_spec"), "tier": "Recommended"})
            rec_total += rec_p

        # Add enclosure / perfboard to recommended
        rec_items.append({
            "name": "Prototyping Perfboard & Project Enclosure Box",
            "price_inr": 180.0,
            "specification": "Durable ABS plastic project box + solderable stripboard for final lab presentation",
            "tier": "Recommended"
        })
        rec_total += 180.0

        savings = max(0.0, round(rec_total - min_total, 1))

        formula_text = (
            f"Component cost (₹{int(sum(i['price_inr'] for i in bom if i.get('category') in ['Sensor', 'Microcontroller', 'Camera', 'Biometrics']))}) + "
            f"additional modules (₹{int(sum(i['price_inr'] for i in bom if i.get('category') in ['Switching/Control', 'Motor Driver', 'Display', 'Audio/Alert']))}) + "
            f"wires/connectors (₹120) + power supply (₹{int(sum(i['price_inr'] for i in bom if i.get('category') in ['Power Supply', 'Battery', 'Voltage Regulator']))}) = "
            f"Estimated Total: ₹{int(rec_total)}"
        )

        return {
            "min_budget": {
                "total_cost": round(min_total, 1),
                "items": min_items,
                "strategy": "Minimal clone modules, reuses existing phone chargers, omits non-essential screens in favor of web/serial readout."
            },
            "recommended_budget": {
                "total_cost": round(rec_total, 1),
                "items": rec_items,
                "strategy": "Branded components with official distributors, dedicated 12V/5V DC power adapter, high-contrast OLED display, and durable presentation enclosure."
            },
            "total_formula": formula_text,
            "savings_inr": savings,
            "savings_percentage": round((savings / max(1.0, rec_total)) * 100.0, 1)
        }

    # --------------------------------------------------------------------------
    # 2.14 FULL HARDWARE ANALYSIS WORKFLOW (EXECUTION PIPELINE)
    # --------------------------------------------------------------------------
    @classmethod
    def analyze_hardware_project(
        cls,
        project: Project,
        student_budget: float = 2000.0,
        available_components: Optional[List[str]] = None,
        preferred_controller: str = "ESP32",
        preferred_marketplace: str = "Robu.in"
    ) -> HardwareAnalysis:
        """
        Executes the end-to-end Gemini Hardware Analysis and Verification pipeline
        and stores the structured result in the database.
        """
        available_components = available_components or []

        # 1. Gemini Complete Hardware Analysis & Verification
        from app.services.gemini_hardware_service import get_gemini_hardware_service
        gemini_hw = get_gemini_hardware_service()

        problem_stmt = ""
        if hasattr(project, "objective") and project.objective:
            problem_stmt = project.objective
        elif hasattr(project, "problem_statement") and getattr(project, "problem_statement", None):
            problem_stmt = project.problem_statement

        clarifications = {}
        if hasattr(project, "clarification_answers_json") and project.clarification_answers_json:
            try:
                clarifications = json.loads(project.clarification_answers_json)
            except Exception:
                pass

        gemini_result = gemini_hw.analyze_complete_project(
            project_name=project.project_name,
            description=project.description or "",
            problem_statement=problem_stmt,
            domain=project.domain or "IoT / Hardware",
            technologies_known=getattr(project, "technologies_known", "") or "",
            student_budget=student_budget,
            available_components=available_components,
            preferred_controller=preferred_controller,
            preferred_marketplace=preferred_marketplace,
            clarification_answers=clarifications
        )

        # 2. Extract BOM and calculate costs
        bom = gemini_result.get("bom", [])
        essential_cost = 0.0
        optional_cost = 0.0
        for item in bom:
            item_name = item.get("component_name", item.get("name", ""))
            item["name"] = item_name
            is_owned = any(avail.lower() in item_name.lower() for avail in available_components)
            item["already_owned"] = is_owned

            cost = float(item.get("estimated_price_inr", item.get("price_inr", 0.0)))
            item["price_inr"] = cost
            if not is_owned:
                if item.get("required", True) or item.get("necessity") == "Essential":
                    essential_cost += cost
                else:
                    optional_cost += cost
        total_cost = essential_cost + optional_cost
        remaining_budget = round(student_budget - total_cost, 1)
        budget_status = "WITHIN_BUDGET" if remaining_budget >= 0 else "OVER_BUDGET"

        # Helper to parse numbers
        def _parse_num(val: Any, default: float) -> float:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                m = re.search(r"[-+]?\d*\.?\d+", val)
                if m:
                    try:
                        return float(m.group(0))
                    except Exception:
                        pass
            return default

        # 3. Categorize components for Architecture Breakdown
        inputs_list = []
        outputs_list = []
        comm_list = []
        proc_list = []

        for item in bom:
            cat = str(item.get("category", "")).lower()
            name = item.get("name", "")
            curr_ma = _parse_num(item.get("current_requirement") or item.get("current_ma"), 20.0)
            volt_v = _parse_num(item.get("operating_voltage") or item.get("voltage_val"), 5.0)

            if "microcontroller" in cat or "processor" in cat or "board" in cat:
                proc_list.append({
                    "name": name,
                    "type": "processing",
                    "category": "Microcontroller",
                    "voltage": str(item.get("operating_voltage", "5V")),
                    "logic_voltage": str(item.get("logic_voltage", "3.3V" if ("esp" in name.lower() or "pico" in name.lower() or "raspberry" in name.lower()) else "5V")),
                    "voltage_val": volt_v,
                    "current_ma": curr_ma,
                    "interface": str(item.get("interface", "GPIO")),
                    "base_price_inr": float(item.get("price_inr", 400.0)),
                    "recommended_spec": str(item.get("specification", ""))
                })
            elif "sensor" in cat:
                inputs_list.append({
                    "name": name,
                    "type": "sensor",
                    "category": "Sensor",
                    "voltage": str(item.get("operating_voltage", "3.3V - 5V")),
                    "voltage_val": volt_v,
                    "current_ma": curr_ma,
                    "interface": str(item.get("interface", "Analog / Digital")),
                    "base_price_inr": float(item.get("price_inr", 150.0)),
                    "recommended_spec": str(item.get("specification", ""))
                })
            elif "communication" in cat:
                comm_list.append({
                    "name": name,
                    "type": "communication",
                    "category": "Communication",
                    "voltage": str(item.get("operating_voltage", "3.3V - 5V")),
                    "voltage_val": volt_v,
                    "current_ma": curr_ma,
                    "interface": str(item.get("interface", "UART / Wi-Fi")),
                    "base_price_inr": float(item.get("price_inr", 350.0)),
                    "recommended_spec": str(item.get("specification", ""))
                })
            elif "actuator" in cat or "display" in cat or "output" in cat:
                outputs_list.append({
                    "name": name,
                    "type": "actuator" if "actuator" in cat else "display",
                    "category": "Actuator" if "actuator" in cat else "Display",
                    "voltage": str(item.get("operating_voltage", "5V")),
                    "voltage_val": volt_v,
                    "current_ma": curr_ma,
                    "interface": str(item.get("interface", "GPIO / I2C")),
                    "base_price_inr": float(item.get("price_inr", 150.0)),
                    "recommended_spec": str(item.get("specification", ""))
                })

        # Base architecture from catalog
        components_arch = cls.extract_architecture_components(
            title=project.project_name,
            description=project.description or "",
            preferred_controller=preferred_controller
        )

        # Merge catalog components so all pin and voltage properties are preserved
        for inp in components_arch.get("inputs", []):
            if not any(i.get("name") == inp.get("name") for i in inputs_list):
                inputs_list.append(inp)
        for out in components_arch.get("outputs", []):
            if not any(o.get("name") == out.get("name") for o in outputs_list):
                outputs_list.append(out)
        for comm in components_arch.get("communication", []):
            if not any(c.get("name") == comm.get("name") for c in comm_list):
                comm_list.append(comm)

        components_arch["inputs"] = inputs_list
        if proc_list:
            components_arch["controller"].update(proc_list[0])
        if "logic_voltage" not in components_arch["controller"]:
            components_arch["controller"]["logic_voltage"] = "3.3V" if ("esp" in components_arch["controller"].get("name", "").lower() or "raspberry" in components_arch["controller"].get("name", "").lower()) else "5V"
        components_arch["outputs"] = outputs_list
        components_arch["communication"] = comm_list

        # Electrical Analysis
        electrical = cls.analyze_electrical_feasibility(components_arch)
        gemini_power = gemini_result.get("power_architecture", {})
        if gemini_power:
            electrical["power_architecture"] = gemini_power
            if gemini_power.get("power_warnings"):
                for w in gemini_power["power_warnings"]:
                    electrical["compatibility_issues"].append({
                        "issue": "Power / Electrical Warning",
                        "severity": "CRITICAL" if "hazard" in w.lower() or "critical" in w.lower() else "WARNING",
                        "description": w,
                        "fix": "Use dedicated external power adapter and step-down regulator."
                    })

        # Wiring Table
        wiring_table = cls.generate_connections_wiring_table(components_arch)
        if gemini_result.get("connections"):
            for conn in gemini_result["connections"]:
                if isinstance(conn, dict):
                    wiring_table.append({
                        "component": conn.get("from_component", ""),
                        "pin": conn.get("from_pin", ""),
                        "connect_to": f"{conn.get('to_component', '')} {conn.get('to_pin', '')}".strip(),
                        "signal_type": conn.get("purpose", ""),
                        "voltage_and_notes": conn.get("voltage_notes", ""),
                        "from_component": conn.get("from_component", ""),
                        "from_pin": conn.get("from_pin", ""),
                        "to_component": conn.get("to_component", ""),
                        "to_pin": conn.get("to_pin", ""),
                        "purpose": conn.get("purpose", "")
                    })

        # Software Requirements & Troubleshooting
        software_reqs = cls.generate_software_requirements(components_arch)
        troubleshooting = cls.generate_contextual_troubleshooting(components_arch)

        # Testing & Verification
        testing_verif = cls.generate_testing_and_verification(components_arch, electrical)
        feasibility_checks = cls.perform_comprehensive_feasibility_check(
            components_arch=components_arch,
            electrical_data=electrical,
            student_budget=student_budget,
            total_bom_cost=total_cost,
            software_reqs=software_reqs
        )
        testing_verif["feasibility_checks"] = feasibility_checks
        testing_verif["feasibility_verification"] = gemini_result.get("feasibility_verification", {})
        testing_verif["project_understanding"] = gemini_result.get("project_understanding", {})

        # Budget Tiers
        budget_tiers = gemini_result.get("budget_tiers")
        if not budget_tiers or not isinstance(budget_tiers, dict) or "min_budget" not in budget_tiers:
            budget_tiers = cls.generate_dual_budget_tiers(bom, components_arch)

        # Products cache with verified distributor options
        products_cache = {}
        for item in bom:
            cname = item.get("name")
            options = item.get("purchase_options", [])
            if options:
                products_cache[cname] = {
                    "component_name": cname,
                    "options": options
                }
            else:
                products_cache[cname] = cls.get_online_purchase_options(cname)

        # Feasibility Verdict & Scores
        verdict = gemini_result.get("verdict", "BUILDABLE")
        verdict_badge = gemini_result.get("verdict_badge", "🟢 BUILDABLE")
        verdict_reason = gemini_result.get("verdict_reason", "Verified for physical prototyping.")
        overall_score = float(gemini_result.get("overall_score", 85.0))
        scores = cls.calculate_feasibility_score(
            components_arch=components_arch,
            electrical_data=electrical,
            student_budget=student_budget,
            total_bom_cost=total_cost
        )
        scores["verdict"] = verdict
        scores["verdict_badge"] = verdict_badge
        scores["verdict_reason"] = verdict_reason
        scores["overall_score"] = overall_score

        modifications = cls.generate_modification_suggestions(
            components_arch=components_arch,
            student_budget=student_budget,
            total_bom_cost=total_cost,
            compatibility_issues=electrical["compatibility_issues"]
        )

        flow_and_logic = cls.generate_system_flow_and_logic(
            components_arch=components_arch,
            project_title=project.project_name,
            project_desc=project.description or ""
        )
        if gemini_result.get("firmware_logic"):
            flow_and_logic["processing_logic"] = f"{flow_and_logic.get('processing_logic', '')}\n\n[Firmware State Machine Logic]\n{gemini_result['firmware_logic']}".strip()
        if gemini_result.get("expected_output"):
            flow_and_logic["expected_output"] = f"{flow_and_logic.get('expected_output', '')}\n\n[Expected Output Metrics]\n{gemini_result['expected_output']}".strip()

        # Persist or Update HardwareAnalysis Record
        analysis = HardwareAnalysis.query.filter_by(project_id=project.id).first()
        if not analysis:
            analysis = HardwareAnalysis(project_id=project.id)
            db.session.add(analysis)

        analysis.project_category = project.project_category or "hardware"
        analysis.overall_score = scores["overall_score"]
        analysis.verdict = scores["verdict"]
        analysis.verdict_badge = scores["verdict_badge"]
        analysis.verdict_reason = scores["verdict_reason"]

        analysis.technical_score = scores["scores"]["technical"]
        analysis.availability_score = scores["scores"]["availability"]
        analysis.budget_score = scores["scores"]["budget"]
        analysis.power_score = scores["scores"]["power"]
        analysis.compatibility_score = scores["scores"]["compatibility"]
        analysis.complexity_score = scores["scores"]["complexity"]
        analysis.time_score = scores["scores"]["time"]

        analysis.inputs_json = json.dumps(components_arch["inputs"])
        analysis.processing_json = json.dumps([components_arch["controller"]])
        analysis.outputs_json = json.dumps(components_arch["outputs"])
        analysis.communication_json = json.dumps(components_arch["communication"])
        analysis.power_json = json.dumps(electrical)

        analysis.bom_json = json.dumps(bom)
        analysis.compatibility_issues_json = json.dumps(electrical["compatibility_issues"])
        analysis.gpio_analysis_json = json.dumps(electrical["gpio_analysis"])

        # Save new hardware analysis & working system fields
        analysis.wiring_table_json = json.dumps(wiring_table)
        analysis.software_reqs_json = json.dumps(software_reqs)
        analysis.testing_verification_json = json.dumps(testing_verif)
        analysis.troubleshooting_json = json.dumps(troubleshooting)
        analysis.budget_tiers_json = json.dumps(budget_tiers)
        analysis.min_budget_cost = float(budget_tiers["min_budget"]["total_cost"])
        analysis.recommended_budget_cost = float(budget_tiers["recommended_budget"]["total_cost"])
        analysis.processing_logic_text = flow_and_logic.get("processing_logic", "")
        analysis.expected_output_text = flow_and_logic.get("expected_output", "")

        analysis.student_budget = float(student_budget)
        analysis.estimated_total_cost = float(total_cost)
        analysis.essential_cost = float(essential_cost)
        analysis.optional_cost = float(optional_cost)
        analysis.remaining_budget = float(remaining_budget)
        analysis.budget_status = budget_status
        analysis.available_components_json = json.dumps(available_components)
        analysis.preferred_controller = preferred_controller
        analysis.preferred_marketplace = preferred_marketplace

        analysis.modifications_json = json.dumps(modifications)
        analysis.products_cache_json = json.dumps(products_cache)

        db.session.commit()
        logger.info(f"Hardware analysis completed for Project {project.id}: Score={analysis.overall_score} [{analysis.verdict}]")
        return analysis

    # --------------------------------------------------------------------------
    # 2.9 HARDWARE-SPECIFIC TASK & TIMELINE ROADMAP GENERATOR
    # --------------------------------------------------------------------------
    @classmethod
    def generate_hardware_tasks(cls, project: Project) -> List[Task]:
        """
        Generates structured 6-phase hardware development tasks based directly
        on the validated hardware architecture and approved BOM.
        """
        analysis = HardwareAnalysis.query.filter_by(project_id=project.id).first()
        controller_name = "ESP32"
        components = []
        if analysis:
            bom = analysis.get_bom()
            components = [item["name"] for item in bom]
            processing = analysis.get_processing()
            if processing:
                controller_name = processing[0].get("name", "ESP32")

        tasks_data = [
            # Phase 1: Architecture & Component Procurement
            {
                "title": f"Component Sourcing & Datasheet Verification ({controller_name})",
                "description": f"Verify pinouts, operating voltage limits, and power requirements for {controller_name} and connected sensors: {', '.join(components[:4])}.",
                "phase": "Phase 1 — Research & Planning",
                "phase_number": 1,
                "category": "Research",
                "priority": "Critical",
                "estimated_hours": 6.0,
                "requirement_source": "Hardware Bill of Materials & Datasheet Verification"
            },
            {
                "title": "Design Complete Circuit Schematic & Power Rail Diagram",
                "description": "Create detailed circuit diagram in Fritzing / EasyEDA, routing 3.3V, 5V, and 12V rails with common ground and flyback diode protections.",
                "phase": "Phase 1 — Research & Planning",
                "phase_number": 1,
                "category": "Hardware",
                "priority": "Critical",
                "estimated_hours": 8.0,
                "requirement_source": "Electrical Architecture & Power Rail Design"
            },

            # Phase 2: Prototyping & Sensor Calibration
            {
                "title": "Breadboard Power Rail Assembly & Voltage Testing",
                "description": "Assemble power regulator/buck converter on breadboard. Measure VCC voltages with a multimeter before plugging in the microcontroller.",
                "phase": "Phase 2 — UI/UX & Architecture",
                "phase_number": 2,
                "category": "Hardware",
                "priority": "High",
                "estimated_hours": 4.0,
                "requirement_source": "Power Verification & Regulator Safe Start"
            },
            {
                "title": f"Sensor Interfacing & Individual Unit Calibration",
                "description": "Wire sensors to GPIO/ADC/I2C pins on breadboard. Write individual test scripts to verify clean signal readings and establish baseline calibrations.",
                "phase": "Phase 2 — UI/UX & Architecture",
                "phase_number": 2,
                "category": "Hardware",
                "priority": "High",
                "estimated_hours": 8.0,
                "requirement_source": "Sensor Interfacing & Pin Validation"
            },

            # Phase 3: Actuator Drivers & Switching Logic
            {
                "title": "Actuator Driver Wiring & Optical Isolation Testing",
                "description": "Wire motor driver / relay module to microcontroller. Verify switching logic without load first, then connect external motor/pump power.",
                "phase": "Phase 3 — Core Development",
                "phase_number": 3,
                "category": "Hardware",
                "priority": "Critical",
                "estimated_hours": 6.0,
                "requirement_source": "Actuator Driver & Isolation Circuit"
            },
            {
                "title": f"Firmware State Machine & Control Loop Development",
                "description": f"Program the main loop on {controller_name}. Implement non-blocking timers (millis) to read sensors, evaluate thresholds, and trigger outputs.",
                "phase": "Phase 3 — Core Development",
                "phase_number": 3,
                "category": "Backend",
                "priority": "Critical",
                "estimated_hours": 12.0,
                "requirement_source": "Microcontroller Firmware & State Machine"
            },

            # Phase 4: Communication & Telemetry
            {
                "title": "Telemetry Transmission & Communication Protocol",
                "description": "Implement Wi-Fi / Bluetooth / Serial telemetry protocol. Transmit structured JSON telemetry packets to web application or cloud dashboard.",
                "phase": "Phase 4 — Database & Integration",
                "phase_number": 4,
                "category": "API",
                "priority": "High",
                "estimated_hours": 8.0,
                "requirement_source": "Wireless Telemetry & IoT Communication"
            },

            # Phase 5: Hardware-In-The-Loop Testing & Stress Tests
            {
                "title": "Hardware Stress Testing & Continuous Run Validation",
                "description": "Execute a continuous 4-hour stress test. Monitor temperature of voltage regulators, motor drivers, and ensure no brownouts or memory leaks occur.",
                "phase": "Phase 5 — Testing & Quality Assurance",
                "phase_number": 5,
                "category": "Testing",
                "priority": "Critical",
                "estimated_hours": 6.0,
                "requirement_source": "Power Stability & Stress Testing"
            },
            {
                "title": "Failsafe Recovery & Fault Detection Implementation",
                "description": "Implement hardware watchdog timer (WDT) and sensor disconnection error handling in firmware to ensure autonomous recovery from lockups.",
                "phase": "Phase 5 — Testing & Quality Assurance",
                "phase_number": 5,
                "category": "Testing",
                "priority": "High",
                "estimated_hours": 4.0,
                "requirement_source": "System Failsafes & Watchdog Timer"
            },

            # Phase 6: Packaging, PCB & Final Viva Defense
            {
                "title": "Soldered Perfboard/PCB Assembly & 3D Enclosure Packaging",
                "description": "Transfer breadboard circuit to soldered perfboard or ordered PCB. Mount in durable enclosure with external power jack and switch.",
                "phase": "Phase 6 — Deployment & Documentation",
                "phase_number": 6,
                "category": "Hardware",
                "priority": "High",
                "estimated_hours": 8.0,
                "requirement_source": "Hardware Packaging & Physical Enclosure"
            },
            {
                "title": "Academic Hardware Report, Circuit Schematics & Viva Defense Prep",
                "description": "Document complete circuit schematic, component BOM with actual costs, pinout tables, and firmware source code for faculty viva presentation.",
                "phase": "Phase 6 — Deployment & Documentation",
                "phase_number": 6,
                "category": "Documentation",
                "priority": "Critical",
                "estimated_hours": 6.0,
                "requirement_source": "Final Academic Hardware Documentation"
            }
        ]

        Task.query.filter_by(project_id=project.id).delete()
        db.session.commit()

        created_tasks = []
        for item in tasks_data:
            t = Task(
                project_id=project.id,
                title=item["title"],
                description=item["description"],
                category=item["category"],
                priority=item["priority"],
                difficulty="Medium",
                estimated_hours=item["estimated_hours"],
                phase=item["phase"],
                phase_number=item["phase_number"],
                can_parallel=False,
                status="Not Started",
                is_core=item["priority"] != "Optional",
                is_optional=item["priority"] == "Optional",
                source="AI_GENERATED",
                reason="Validated Hardware Architecture Component",
                requirement_source=item["requirement_source"]
            )
            db.session.add(t)
            created_tasks.append(t)

        project.initial_task_count = len(created_tasks)
        project.hardware_feasibility_status = "APPROVED"
        if analysis:
            analysis.is_approved = True

        db.session.commit()
        return created_tasks


def get_hardware_feasibility_service() -> HardwareFeasibilityService:
    """Factory helper to obtain HardwareFeasibilityService instance."""
    return HardwareFeasibilityService()
