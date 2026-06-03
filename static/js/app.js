function renderDuration(seconds) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;

  if (hours > 0) {
    return `${hours}小时${minutes}分钟${remainingSeconds}秒`;
  }
  if (minutes > 0) {
    return `${minutes}分钟${remainingSeconds}秒`;
  }
  return `${remainingSeconds}秒`;
}

document.addEventListener("DOMContentLoaded", () => {
  const captchaButton = document.querySelector("[data-refresh-captcha]");
  const captchaImage = document.getElementById("register-captcha");

  if (captchaButton && captchaImage) {
    captchaButton.addEventListener("click", () => {
      captchaImage.src = `/captcha.svg?ts=${Date.now()}`;
    });
  }

  document.querySelectorAll("[data-live-timer]").forEach((element) => {
    const startedAt = element.getAttribute("data-started-at");
    if (!startedAt) {
      return;
    }

    const startTime = new Date(startedAt);
    const update = () => {
      const seconds = (Date.now() - startTime.getTime()) / 1000;
      element.textContent = `已学习 ${renderDuration(seconds)}`;
    };

    update();
    window.setInterval(update, 1000);
  });
});
