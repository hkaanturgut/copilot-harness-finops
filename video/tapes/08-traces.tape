# Shot 8: App Insights spans. Model and shell latency, then every egress decision.
# kql = az monitor app-insights query (last 3 days) printed as a table, account name masked.
Output video/out/08-traces.mp4
Source video/tapes/_setup.tape
Set FontSize 18
Hide
Type "alias kql=video/kql.sh && clear" Enter
Sleep 1s
Show
Set TypingSpeed 12ms
Type `kql 'dependencies | where name in ("execute_tool bash", "chat gpt-5.4-mini") | summarize n=count(), p50_ms=percentile(duration, 50), p90_ms=percentile(duration, 90) by name'`
Enter
Wait+Screen@90s /execute_tool bash +[0-9]/
Sleep 5s
Type `kql 'dependencies | where name startswith "Network egress decision" | summarize count() by name | order by count_ desc | take 12'`
Enter
Wait+Screen@90s /example.com/
Sleep 12s
