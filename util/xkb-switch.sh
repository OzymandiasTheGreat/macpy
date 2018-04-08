#!/bin/bash

script_dir="$(cd "$(dirname "$0")" ; pwd -P)"
start_dir="$(pwd)"
repo="$(git rev-parse --show-toplevel)"

if [ $(basename "$repo") == "macpy" ] ; then
	cd "$repo"
	git submodule update --remote "./xkb-switch"
	cp -f "${script_dir}/xkb-switch_CMakeLists.txt" "${repo}/xkb-switch/CMakeLists.txt"
	cd "${repo}/xkb-switch"
	mkdir -p "build"
	cd "build"
	cmake ..
	make
	cp -f libxkbswitch* "${repo}/macpy/libxkbswitch"
	make clean
	cd ..
	git reset --hard
	git clean -dff
	cd "$start_dir"
fi
