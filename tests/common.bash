#! /usr/bin/env bats

common_setup() {
  # Use $BATS_TEST_FILENAME to get the containing directory of this file
  # instead of ${BASH_SOURCE[0]}, which points to the bats executable, or
  # $0, which points to the preprocessed file.

  # shellcheck disable=SC2034
  TEST_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" >/dev/null 2>&1 && pwd)"
}

assert_output() {
  # This is a light version of the function with the same name in `bats-assert`
  is_mode_partial=0
  while (($# > 0)); do
    case "$1" in
    -p | --partial)
      is_mode_partial=1
      shift
      ;;
    --)
      shift
      break
      ;;
    *) break ;;
    esac
  done

  expected=$1
  if ((is_mode_partial)); then
    # shellcheck disable=SC2154
    if [[ $output != *"$expected"* ]]; then
      echo "-- output does not contain substring --"
      echo "substring $expected"
      echo "output $output"
      echo "--"
      return 1
    fi
  else
    if [[ $output != *"$expected"* ]]; then
      echo "-- output differs --"
      echo "expected $expected"
      echo "actual $output"
      echo "--"
      return 1
    fi
  fi
}
