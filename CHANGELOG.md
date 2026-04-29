# Changelog

## [0.3.0](https://github.com/jjack/hass-remote-boot-manager/compare/v0.2.0...v0.3.0) (2026-04-29)


### Features

* adding broadcast address and port ([54e1695](https://github.com/jjack/hass-remote-boot-manager/commit/54e16951145b96fcfe9718fa233eda235e145898))
* can regenerate the webhook id ([421820a](https://github.com/jjack/hass-remote-boot-manager/commit/421820abb57eee7388345acad3481c1b12ef819e))


### Bug Fixes

* correcting the remote-boot-agent url ([7240ca3](https://github.com/jjack/hass-remote-boot-manager/commit/7240ca31027a8ee53b0952cd3c77ce72a11d5f07))

## [0.2.0](https://github.com/jjack/hass-remote-boot-manager/compare/v0.1.1...v0.2.0) (2026-04-16)


### Features

* adding release please for release versioning ([b509f8a](https://github.com/jjack/hass-remote-boot-manager/commit/b509f8ace50acec9be792220bf24ad3ffc8f8636))
* allowing a custom webhook id ([20e2319](https://github.com/jjack/hass-remote-boot-manager/commit/20e2319bff2a8dfe56471e352479dd1abf5724db))
* can now auto-generate webhook_ids for security ([f8d94e3](https://github.com/jjack/hass-remote-boot-manager/commit/f8d94e36565dc95508262327519b058bf3148285))
* home assistant now starts and lets me almost add the integration ([478848e](https://github.com/jjack/hass-remote-boot-manager/commit/478848efedd8ef9ad5b2f53e918cee25f88d91cc))


### Bug Fixes

* adding missing wakeonlan dependency ([23f5114](https://github.com/jjack/hass-remote-boot-manager/commit/23f51140726e3b7311e74b90ff694fbd7ca6e022))
* adding new platforms and removing dead code ([b444908](https://github.com/jjack/hass-remote-boot-manager/commit/b4449082f158c16fe2ef7da2199d67607a861985))
* better handlig of custom types ([0ed7f4c](https://github.com/jjack/hass-remote-boot-manager/commit/0ed7f4c1f73ea8319755dcf1cc2c138b9d057501))
* better handling an empty os list ([6295d92](https://github.com/jjack/hass-remote-boot-manager/commit/6295d923d94a4e196fa16dc792cab4196ac102c2))
* better handling of missing json ([e8ff2b2](https://github.com/jjack/hass-remote-boot-manager/commit/e8ff2b26f79ea8c87df8e611bcc602ee500e863c))
* can now select an OS for real ([1d3121a](https://github.com/jjack/hass-remote-boot-manager/commit/1d3121a0a28f4938bd26e4fb6a2b8b8a54eb070e))
* consuming boot config so that it doesn't persist ([db3d405](https://github.com/jjack/hass-remote-boot-manager/commit/db3d405f2727fc37532fbe00f963338a2f2b89a3))
* dropping the homeassistant package down even more, because it's the latest available in the CI ([b877c4d](https://github.com/jjack/hass-remote-boot-manager/commit/b877c4dcf1560a43a14ca5b226a093dd627901fb))
* ensuring mac address is present in the bootloader get request ([aa1370c](https://github.com/jjack/hass-remote-boot-manager/commit/aa1370c414337a63382d4a995c521f2703b73856))
* fixing documentation url in config flow ([7aebc00](https://github.com/jjack/hass-remote-boot-manager/commit/7aebc00837e12cf9224e13a98d237fe83123ff98))
* fixing hostname in device info ([0f1f720](https://github.com/jjack/hass-remote-boot-manager/commit/0f1f7209392d74407a15df32654f20059bc59752))
* fixing issue with test and possible None values ([56a0d45](https://github.com/jjack/hass-remote-boot-manager/commit/56a0d45bb997f86935dcbb449ae02bdd4f41b12c))
* fixing log message variable ([3945939](https://github.com/jjack/hass-remote-boot-manager/commit/3945939dab23e5d97b30b9551c805bab4654a31b))
* fixing sync/async handling of bootloaders ([1139e59](https://github.com/jjack/hass-remote-boot-manager/commit/1139e590fa1b13eff53bdf2c1d6a348f4f080548))
* handling new/old servers a little differently ([28d4131](https://github.com/jjack/hass-remote-boot-manager/commit/28d41317212211288df66a4ba4196cedcf0835d5))
* linting and adding missing wakeonlan dependency ([8fdf601](https://github.com/jjack/hass-remote-boot-manager/commit/8fdf6017247edcf04bf00e4ebd381fad186c35e2))
* no longer consuming the next boot option immediately so that it can actually get picked up in the boot process ([1d11478](https://github.com/jjack/hass-remote-boot-manager/commit/1d11478da655aca53a15a1f1a8920d3213e941f1))
* normalizing mac addresses ([9308f2c](https://github.com/jjack/hass-remote-boot-manager/commit/9308f2ce5cd6de897aef7059ed0d0c8e6883bfd0))
* registering/unregistering views to prevent memory issues ([9a30b83](https://github.com/jjack/hass-remote-boot-manager/commit/9a30b83a66fafcba21ffeadaab1eaefbfd0b0d2f))
* removing busted is_new logic ([7713d05](https://github.com/jjack/hass-remote-boot-manager/commit/7713d05a2688f00da23f20010af6e0bdff0f8bc5))
* removing busted is_new logic for servers ([beb6e83](https://github.com/jjack/hass-remote-boot-manager/commit/beb6e83a55c1ff0d88a85cd5e7eba83dada8e35d))
* reset the OS when the button gets pressed ([6d97571](https://github.com/jjack/hass-remote-boot-manager/commit/6d975717584feecd7ff76a9153273a76eb7097c9))
* saving boot manager state across hass restarts ([ca4de54](https://github.com/jjack/hass-remote-boot-manager/commit/ca4de54765d1a64a55fbddd95c7bf3c8c7226783))
* this hasn't been called netboot manager in a while ([55fafbc](https://github.com/jjack/hass-remote-boot-manager/commit/55fafbcd741d825e52003d2e27b110dca2c8c4e9))
* updating ha device registry when hostnames change ([35dce1e](https://github.com/jjack/hass-remote-boot-manager/commit/35dce1e2be7597cf6a7d0745059dc4acdc7fc66a))
* updating issue_tracker string to the correct url ([c47f7b6](https://github.com/jjack/hass-remote-boot-manager/commit/c47f7b62b10275712e49d06a346c7387bd6e2add))
* updating manager to handle the incoming webhook ([62ce29a](https://github.com/jjack/hass-remote-boot-manager/commit/62ce29a93d79e3749e5dbf54300ba1be62fb728b))
* using .venv ruff command for linting ([9f96b65](https://github.com/jjack/hass-remote-boot-manager/commit/9f96b6583dde923367c0aff87101e9d3f5419f4e))
* using correct act location for github local actions ([19f5356](https://github.com/jjack/hass-remote-boot-manager/commit/19f53567b97d3710aef012bbfe05253d4270e097))
* using correct name for boot config generation ([10107a2](https://github.com/jjack/hass-remote-boot-manager/commit/10107a2027f7da9150027755b13a0818d2f5b43d))
* using working version of homeassistant package ([31e7534](https://github.com/jjack/hass-remote-boot-manager/commit/31e7534ebe968a5ca63b4f5006eb3197d84b5be6))


### Documentation

* added README ([2d07d3c](https://github.com/jjack/hass-remote-boot-manager/commit/2d07d3c5e525bd58a4e42f0cfc8861e90b21afa2))
* correcting webhook id display ([77b701e](https://github.com/jjack/hass-remote-boot-manager/commit/77b701e8ad22f5ade971f3a027ede7bee9ec5ec8))
