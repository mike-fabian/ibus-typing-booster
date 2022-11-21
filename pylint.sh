#!/bin/bash

CURRENT_DIR="$(pwd)"
# get the full path of the directory where the current script is:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

FILES_WITH_ERRORS=''

echo "running $SCRIPT_DIR/pylint.sh"

PYLINT="pylint-3"

CHECK_DIR=${SCRIPT_DIR}/engine
echo ${CHECK_DIR}
cd ${CHECK_DIR}
for i in *.py
do
    echo ${PYLINT} ${i}
    ${PYLINT} ${i}
    if [ $? != 0 ] ; then
        FILES_WITH_ERRORS="${FILES_WITH_ERRORS} ${CHECK_DIR}/${i}"
    fi
done
CHECK_DIR=${SCRIPT_DIR}/setup
echo ${CHECK_DIR}
cd ${CHECK_DIR}
for i in *.py
do
    if [ ${i} != 'user_transliteration.py' ] ; then
        echo ${PYLINT} ${i}
        ${PYLINT} ${i}
        if [ $? != 0 ] ; then
            FILES_WITH_ERRORS="${FILES_WITH_ERRORS} ${CHECK_DIR}/${i}"
        fi
    fi
done
CHECK_DIR=${SCRIPT_DIR}/tests
echo ${CHECK_DIR}
cd ${CHECK_DIR}
for i in *.py
do
    echo ${PYLINT} ${i}
    ${PYLINT} ${i}
    if [ $? != 0 ] ; then
        FILES_WITH_ERRORS="${FILES_WITH_ERRORS} ${CHECK_DIR}/${i}"
    fi
done

cd $CURRENT_DIR
echo "These files had errors: “${FILES_WITH_ERRORS}”"
exit 0



