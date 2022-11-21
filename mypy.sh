#!/bin/bash

CURRENT_DIR="$(pwd)"
# get the full path of the directory where the current script is:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

RETVAL=0

echo "running $SCRIPT_DIR/mypy.sh"

MYPY="mypy --strict --show-error-codes --pretty"

echo cd $SCRIPT_DIR/engine
cd $SCRIPT_DIR/engine
echo ${MYPY} *.py
${MYPY} *.py
ENGINE_RETVAL=$?
if [ ${ENGINE_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${ENGINE_RETVAL}))
fi

echo cd $SCRIPT_DIR/setup
cd $SCRIPT_DIR/setup
echo ${MYPY} ../engine/{tabsqlitedb,itb_util,itb_emoji}.py *.py
${MYPY} ../engine/{tabsqlitedb,itb_util,itb_emoji}.py *.py
SETUP_RETVAL=$?
if [ ${SETUP_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${SETUP_RETVAL}))
fi

echo cd $SCRIPT_DIR/tests
cd $SCRIPT_DIR/tests
echo ${MYPY} ../engine/{tabsqlitedb,itb_util,itb_emoji}.py test_*.py
${MYPY} ../engine/{tabsqlitedb,itb_util,itb_emoji}.py test_*.py
SETUP_RETVAL=$?
if [ ${SETUP_RETVAL} != 0 ] ; then
    RETVAL=$((${RETVAL} + ${SETUP_RETVAL}))
fi

cd $CURRENT_DIR
exit $RETVAL



