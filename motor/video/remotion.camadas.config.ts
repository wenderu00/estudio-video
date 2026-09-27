// Config used only for the transparent overlay clips of the video mode (the main config sets a CRF,
// which ProRes rejects).
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png");
Config.setConcurrency(4);
Config.setChromiumOpenGlRenderer("swangle");
Config.setCodec("prores");
Config.setProResProfile("4444");
Config.setPixelFormat("yuva444p10le");
