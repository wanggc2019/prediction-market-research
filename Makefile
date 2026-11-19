.PHONY: launchd

# make launchd module=pm-trending action=install|uninstall|status [interval=秒]
launchd:
	@test -n "$(module)" || (echo "用法：make launchd module=pm-trending action=status"; exit 2)
	@INTERVAL=$(or $(interval),3600) bash tools/launchd.sh $(module) $(or $(action),status)
