import React, { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface RevealProps {
  children: React.ReactNode;
  width?: "fit-content" | "100%";
  stagger?: boolean;
  delay?: number;
}

export const Reveal = ({
  children,
  width = "fit-content",
  stagger = false,
  delay = 0,
}: RevealProps) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-10% 0px" });

  if (stagger) {
    // For staggered text (assumes children is a string or simple elements)
    // We will just do a simple stagger children if it's a wrapper, or we can use it to stagger block elements.
    // To keep it safe for any children, we'll just do a container with staggerChildren.
    const containerVariants = {
      hidden: { opacity: 0 },
      visible: {
        opacity: 1,
        transition: {
          staggerChildren: 0.1,
          delayChildren: delay,
        },
      },
    };
    return (
      <motion.div
        ref={ref}
        variants={containerVariants}
        initial="hidden"
        animate={isInView ? "visible" : "hidden"}
        style={{ width }}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <div ref={ref} style={{ position: "relative", width, overflow: "hidden" }}>
      <motion.div
        variants={{
          hidden: { opacity: 0, y: 16 },
          visible: { opacity: 1, y: 0 },
        }}
        initial="hidden"
        animate={isInView ? "visible" : "hidden"}
        // The app's --ease-out and a --dur-slow-scale duration (tokens.css).
        transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1], delay }}
      >
        {children}
      </motion.div>
    </div>
  );
};
