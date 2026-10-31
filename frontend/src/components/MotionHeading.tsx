import { Fragment, useLayoutEffect, useRef } from "react";
export default function MotionHeading({ text }: { text: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    const heading = ref.current!;
    const align = () => {
      let previous = -1,
        line = -1;
      for (const word of heading.querySelectorAll<HTMLElement>(".word-mask")) {
        if (word.offsetTop !== previous) {
          line++;
          previous = word.offsetTop;
        }
        word.style.setProperty("--delay", line * 0.085 + "s");
      }
    };
    align();
    const observer = new ResizeObserver(align);
    observer.observe(heading);
    return () => observer.disconnect();
  }, [text]);
  return (
    <h1 className="motion-heading" ref={ref} aria-label={text}>
      {text.split(" ").map((word, i) => (
        <Fragment key={i}>
          {i > 0 && " "}
          <span className="word-mask">
            <span>{word}</span>
          </span>
        </Fragment>
      ))}
    </h1>
  );
}
