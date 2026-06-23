function confirmDelete() {
    return confirm("Вы уверены, что хотите удалить эту задачу?");
}

function confirmUserDelete() {
    return confirm("Удалить пользователя? Его задачи останутся без исполнителя.");
}

function renderUsageSteps() {
    const roots = document.querySelectorAll(".usage-steps-root");

    if (!roots.length) {
        return;
    }

    const steps = [
        {
            title: "Зарегистрируйся",
            icon: "/static/icons/add_user_icon..png",
        },
        {
            title: "Создай проект",
            icon: "/static/icons/project.png",
        },
        {
            title: "Добавляй задачи",
            icon: "/static/icons/task_icon.png",
        },
    ];

    roots.forEach((root) => {
        root.innerHTML = `
            <h2 class="usage-steps-title">Просто в использовании</h2>
            <div class="usage-steps-panel">
                ${steps.map((step, index) => `
                    <article class="usage-step" style="--step-delay: ${index * 360}ms">
                        <div class="usage-step-icon">
                            <img src="${step.icon}" alt="" aria-hidden="true">
                        </div>
                        <h3>${step.title}</h3>
                    </article>
                `).join("")}
            </div>
        `;

        const panel = root.querySelector(".usage-steps-panel");

        if (!("IntersectionObserver" in window)) {
            panel.classList.add("is-visible");
            return;
        }

        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                panel.classList.add("is-visible");
                observer.disconnect();
            }
        }, { threshold: 0.25 });

        observer.observe(panel);
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderUsageSteps);
} else {
    renderUsageSteps();
}
