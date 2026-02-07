#!/bin/bash
cd /mnt/c/Users/andst/CHTEXT
source venv/bin/activate

echo "=== Help Output ===" > test_output.txt
python main.py --help >> test_output.txt 2>&1

echo "" >> test_output.txt
echo "=== List Command ===" >> test_output.txt
python main.py list >> test_output.txt 2>&1

echo "" >> test_output.txt
echo "=== Random Command ===" >> test_output.txt
python main.py random >> test_output.txt 2>&1

echo "" >> test_output.txt
echo "=== Stats Command ===" >> test_output.txt
python main.py stats >> test_output.txt 2>&1

echo "Tests completed, see test_output.txt"
