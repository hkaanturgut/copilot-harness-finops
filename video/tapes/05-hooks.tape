# Shot 5: postprovision (App Insights + egress policy) and postdeploy (agent identity role).
Output video/out/05-hooks.mp4
Source video/tapes/_setup.tape
Set FontSize 18
Hide
Type "alias view='pygmentize -O style=monokai -f terminal256' && clear" Enter
Sleep 1s
Show
Set TypingSpeed 20ms
Type "view scripts/postprovision.sh | sed -n '33,47p'"
Enter
Sleep 12s
Type "clear && view scripts/assign-agent-role.sh | sed -n '9,31p'"
Enter
Sleep 11s
