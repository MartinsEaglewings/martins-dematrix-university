document.addEventListener("DOMContentLoaded", () => {

    // Smooth scrolling for portal sections
    document.querySelectorAll('a[href^="#"]').forEach(link => {

        link.addEventListener("click", event => {

            const targetId = link.getAttribute("href");

            if (targetId === "#") return;

            const target = document.querySelector(targetId);

            if (target) {
                event.preventDefault();

                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

                document.querySelectorAll(".sidebar a").forEach(item => {
                    item.classList.remove("active");
                });

                if (link.closest(".sidebar")) {
                    link.classList.add("active");
                }
            }

        });

    });


    // Highlight sidebar item according to visible section
    const sections = document.querySelectorAll(".portal-section");

    const observer = new IntersectionObserver(entries => {

        entries.forEach(entry => {

            if (entry.isIntersecting) {

                const id = entry.target.id;

                document.querySelectorAll(".sidebar a").forEach(link => {
                    link.classList.remove("active");

                    if (link.getAttribute("href") === "#" + id) {
                        link.classList.add("active");
                    }
                });

            }

        });

    }, {
        threshold: 0.2,
        rootMargin: "-80px 0px -50% 0px"
    });


    sections.forEach(section => observer.observe(section));


    // Add small interaction to buttons
    document.querySelectorAll(".primary-btn").forEach(button => {

        button.addEventListener("click", () => {
            button.style.transform = "scale(.97)";

            setTimeout(() => {
                button.style.transform = "";
            }, 120);
        });

    });

});
