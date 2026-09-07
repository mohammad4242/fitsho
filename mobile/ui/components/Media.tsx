import {
  Image,
  StyleSheet,
  type ImageProps,
  type ImageSourcePropType,
  type ImageStyle,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { VideoView, type VideoSource, type VideoViewProps, useVideoPlayer } from "expo-video";

import { fiticianTokens } from "../tokens";

export interface ImageMediaProps extends Omit<ImageProps, "accessibilityLabel" | "source" | "style"> {
  readonly accessibilityLabel?: string;
  readonly kind?: "image";
  readonly source: ImageSourcePropType;
  readonly style?: StyleProp<ImageStyle>;
}

export interface VideoMediaProps extends Omit<VideoViewProps, "accessibilityLabel" | "player" | "style"> {
  readonly accessibilityLabel?: string;
  readonly autoplay?: boolean;
  readonly kind: "video";
  readonly loop?: boolean;
  readonly muted?: boolean;
  readonly source: VideoSource;
  readonly style?: StyleProp<ViewStyle>;
}

export type MediaProps = ImageMediaProps | VideoMediaProps;

export function Media(props: MediaProps) {
  if (props.kind === "video") {
    return <VideoMedia {...props} />;
  }

  const { accessibilityLabel, kind: _kind, source, style, ...imageProps } = props;
  return (
    <Image
      {...imageProps}
      accessibilityLabel={accessibilityLabel}
      resizeMode={imageProps.resizeMode ?? "cover"}
      source={source}
      style={[styles.image, style]}
    />
  );
}

function VideoMedia({
  accessibilityLabel,
  autoplay = false,
  kind: _kind,
  loop = false,
  muted = true,
  source,
  style,
  ...videoProps
}: VideoMediaProps) {
  const player = useVideoPlayer(source, (instance) => {
    instance.loop = loop;
    instance.muted = muted;
    if (autoplay) {
      instance.play();
    }
  });

  return (
    <VideoView
      {...videoProps}
      accessibilityLabel={accessibilityLabel}
      contentFit={videoProps.contentFit ?? "cover"}
      nativeControls={videoProps.nativeControls ?? false}
      player={player}
      style={[styles.video, style]}
    />
  );
}

const styles = StyleSheet.create({
  image: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.medium,
  },
  video: {
    backgroundColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.medium,
    minHeight: 180,
    overflow: "hidden",
  },
});
