#!/bin/bash
figlet `hostname -f` -w 200 | /usr/games/lolcat -f
echo IP: `host \`hostname\` | cut -d' ' -f4` | figlet -w 200 | /usr/games/lolcat -f
