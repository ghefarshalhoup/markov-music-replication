import { useEffect } from 'react';

// Entrance for each new screen (Animate.css). React decides which screen shows; this only animates it.
// Every new screen starts at the top of the page.
export default function AnimatedScreen({ children, wide = false, label }) {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <main
      className={`screen animate__animated animate__fadeInUp${wide ? ' screen--wide' : ''}`}
      aria-label={label}
    >
      {children}
    </main>
  );
}
