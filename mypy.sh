#!/bin/bash

CURRENT_DIR="$(pwd)"
# get the full path of the directory where the current script is:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

RETVAL=0

echo "running $SCRIPT_DIR/mypy.sh"

cd $SCRIPT_DIR/engine
echo "Checking $SCRIPT_DIR/engine"
mypy --strict *.py
ENGINE_RETVAL=$?
if [ ${ENGINE_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${ENGINE_RETVAL}))
fi

cd $SCRIPT_DIR/setup
echo "Checking $SCRIPT_DIR/setup"
mypy --strict ../engine/{tabsqlitedb,itb_util,itb_emoji}.py *.py
SETUP_RETVAL=$?
if [ ${SETUP_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${SETUP_RETVAL}))
fi

cd $SCRIPT_DIR/tests
echo "Checking $SCRIPT_DIR/tests"
mypy --strict ../engine/{tabsqlitedb,itb_util,itb_emoji}.py test_*.py
SETUP_RETVAL=$?
if [ ${SETUP_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${SETUP_RETVAL}))
fi

cd $CURRENT_DIR
exit $RETVAL



