#!/bin/bash
# Project Initialization & System Check
# Validates all project components before deployment

echo "🌱 Greenhouse Automation System - Initialize & Verify"
echo "======================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
errors=0
warnings=0

# 1. Project Structure
echo "📁 Checking project structure..."
required_dirs=(
    "rt_controller"
    "sensors"
    "firebase_sync"
    "dashboard"
    "config"
    "docs"
)

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ✅ $dir/"
    else
        echo -e "  ${RED}❌ $dir/ - MISSING${NC}"
        ((errors++))
    fi
done

echo ""

# 2. Required Files
echo "📄 Checking required files..."
required_files=(
    "rt_controller/greenhouse_controller.c"
    "rt_controller/Makefile"
    "sensors/sensor_simulator.py"
    "firebase_sync/firebase_sync.py"
    "dashboard/index.html"
    "config/mosquitto.conf"
    "docs/INSTALLATION.md"
    "docs/GETTING_STARTED.md"
    "docs/FIREBASE_SETUP.md"
    "README.md"
    "requirements.txt"
    "Makefile"
    "quickstart.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ✅ $file"
    else
        echo -e "  ${RED}❌ $file - MISSING${NC}"
        ((errors++))
    fi
done

echo ""

# 3. C Compilation Check
echo "🔨 Checking C compilation..."
if command -v gcc &> /dev/null; then
    echo -e "  ✅ GCC installed"
    
    # Try to compile
    if cd rt_controller && make clean &> /dev/null && make &> /dev/null; then
        if [ -f "greenhouse_controller" ]; then
            echo -e "  ✅ RT Controller compiles successfully"
            # Cleanup
            make clean &> /dev/null
        else
            echo -e "  ${RED}❌ Compilation failed - no executable${NC}"
            ((warnings++))
        fi
    else
        echo -e "  ${YELLOW}⚠ Compilation failed (might need libpaho-mqtt-dev)${NC}"
        ((warnings++))
    fi
    cd ..
else
    echo -e "  ${YELLOW}⚠ GCC not found${NC}"
    ((warnings++))
fi

echo ""

# 4. Python Check
echo "🐍 Checking Python..."
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1)
    echo -e "  ✅ Python: $python_version"
    
    # Check paho-mqtt
    if python3 -c "import paho.mqtt" 2>/dev/null; then
        echo -e "  ✅ paho-mqtt installed"
    else
        echo -e "  ${YELLOW}⚠ paho-mqtt NOT installed${NC}"
        echo "    Run: pip install paho-mqtt"
        ((warnings++))
    fi
    
    # Check firebase-admin (optional)
    if python3 -c "import firebase_admin" 2>/dev/null; then
        echo -e "  ✅ firebase-admin installed"
    else
        echo -e "  ${YELLOW}⚠ firebase-admin NOT installed (optional)${NC}"
        echo "    Run: pip install firebase-admin"
        ((warnings++))
    fi
else
    echo -e "  ${RED}❌ Python3 not found${NC}"
    ((errors++))
fi

echo ""

# 5. MQTT Broker Check
echo "📡 Checking MQTT Broker..."
if command -v mosquitto &> /dev/null; then
    mosquitto_version=$(mosquitto --version 2>&1)
    echo -e "  ✅ Mosquitto: $mosquitto_version"
else
    echo -e "  ${YELLOW}⚠ Mosquitto NOT installed${NC}"
    echo "    Run: sudo apt install mosquitto mosquitto-clients"
    ((warnings++))
fi

echo ""

# 6. Documentation Check
echo "📚 Checking documentation..."
docs=(
    "README.md"
    "docs/INSTALLATION.md"
    "docs/GETTING_STARTED.md"
    "docs/FIREBASE_SETUP.md"
    "PROJECT_SUMMARY.md"
)

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        lines=$(wc -l < "$doc")
        echo -e "  ✅ $doc ($lines lines)"
    else
        echo -e "  ${RED}❌ $doc - MISSING${NC}"
        ((errors++))
    fi
done

echo ""

# 7. Script Executability
echo "🔧 Checking scripts..."
if [ -x "quickstart.sh" ]; then
    echo -e "  ✅ quickstart.sh executable"
else
    echo -e "  ${YELLOW}⚠ quickstart.sh not executable${NC}"
    chmod +x quickstart.sh
    echo -e "  ✅ Made executable"
fi

echo ""

# 8. File Size Summary
echo "💾 Project Size:"
total_size=$(du -sh . 2>/dev/null | cut -f1)
echo "  📦 Total: $total_size"

echo ""

# Final Report
echo "======================================================"
echo ""

if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED!${NC}"
    echo ""
    echo "🚀 Ready to deploy!"
    echo ""
    echo "Next steps:"
    echo "  1. Read: docs/GETTING_STARTED.md"
    echo "  2. Run:  ./quickstart.sh"
    echo "  3. Open: http://localhost:8000/dashboard/index.html"
    exit 0
else
    echo -e "${YELLOW}⚠ ${errors} ERROR(S), ${warnings} WARNING(S)${NC}"
    echo ""
    
    if [ $errors -gt 0 ]; then
        echo "❌ ERRORS - Fix before deployment:"
        echo "  • Install missing dependencies"
        echo "  • Ensure all project files are present"
    fi
    
    if [ $warnings -gt 0 ]; then
        echo ""
        echo "⚠ WARNINGS - Recommended fixes:"
        echo "  • Install recommended packages: pip install -r requirements.txt"
        echo "  • Install system dependencies: sudo apt install mosquitto"
    fi
    
    exit 1
fi
