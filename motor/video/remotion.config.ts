import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setConcurrency(6);
Config.setChromiumOpenGlRenderer("swangle");
Config.setCodec("h264");
Config.setCrf(16);
Config.setPixelFormat("yuv420p");
