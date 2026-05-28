document.addEventListener("DOMContentLoaded", function () {
    // Переключение полей доставки
    const belpostRadio = document.getElementById("belpost");
    const europostRadio = document.getElementById("europost");
    const belpostFields = document.getElementById("belpost-fields");
    const europostFields = document.getElementById("europost-fields");

    function updateDeliveryFields() {
      if (belpostRadio && belpostRadio.checked) {
        belpostFields.style.display = "block";
        europostFields.style.display = "none";
      } else if (europostRadio && europostRadio.checked) {
        belpostFields.style.display = "none";
        europostFields.style.display = "block";
      }
    }

    if (belpostRadio)
      belpostRadio.addEventListener("change", updateDeliveryFields);
    if (europostRadio)
      europostRadio.addEventListener("change", updateDeliveryFields);
    updateDeliveryFields();

    // Данные о форматах (мин. количество и цена)
    let formatData = {};
    document.querySelectorAll(".format-select option").forEach((opt) => {
      if (opt.value) {
        formatData[opt.value] = {
          price: parseFloat(opt.dataset.price) || 0,
          minQty: parseInt(opt.dataset.min) || 0,
        };
      }
    });

    // Загрузка фотографий
    let currentFormatIndex = 0;
    let uploadedFiles = {};
    let itemCount = document.querySelectorAll('.order-item').length;

    function updateQuantityAndPrice(formatIndex) {
  const item = document.querySelector(`.upload-photos-btn[data-format-index="${formatIndex}"]`)?.closest(".order-item");
  if (!item) return;
  
  const formatSelect = item.querySelector(".format-select");
  const quantityInput = item.querySelector(".quantity-input");
  const subtotalInput = item.querySelector(".item-subtotal");

  const selectedFormat = formatSelect.value;
  const photoCount = uploadedFiles[formatIndex] ? uploadedFiles[formatIndex].length : 0;

  // Обновляем количество
  quantityInput.value = photoCount;

  // Получаем цену
  const price = formatData[selectedFormat]?.price || 0;

  // Считаем сумму
  const subtotal = price * photoCount;
  subtotalInput.value = subtotal.toFixed(2) + " BYN";

  calculateTotal();
}
    
    function calculateTotal() {
      let total = 0;
      let totalPhotos = 0;

      document.querySelectorAll(".order-item").forEach((item) => {
        const formatSelect = item.querySelector(".format-select");
        const quantity = parseInt(item.querySelector(".quantity-input").value) || 0;
        const selectedOption = formatSelect.options[formatSelect.selectedIndex];
        let price = 0;

        if (selectedOption && selectedOption.dataset.price) {
          price = parseFloat(selectedOption.dataset.price);
        }

        total += price * quantity;
        totalPhotos += quantity;
      });

      let discountApplied = false;
      let discountAmount = 0;
      let originalTotal = total;

      // Применяем скидку от 200 фото
      if (totalPhotos >= 200) {
        discountAmount = total * 0.05; // 5% скидка
        total = total * 0.95;
        discountApplied = true;
      }

      // Обновляем отображение
      document.getElementById("total-amount").textContent = total.toFixed(2);
      document.getElementById("total-photos").textContent = totalPhotos;

      // Показываем информацию о скидке
      const discountInfo = document.getElementById("discount-info");
      if (discountInfo) {
        if (discountApplied) {
          discountInfo.style.display = "block";
          discountInfo.style.color = "green";
          discountInfo.innerHTML = `🎉 Скидка 5% применена! Вы сэкономили ${discountAmount.toFixed(2)} BYN`;
        } else if (totalPhotos > 0) {
          const needMore = 200 - totalPhotos;
          discountInfo.style.display = "block";
          discountInfo.style.color = "#fd7e14";
          discountInfo.innerHTML = `💰 Добавьте еще ${needMore} фото для скидки 5% (экономия ${(originalTotal * 0.05).toFixed(2)} BYN)`;
        } else {
          discountInfo.style.display = "none";
        }
      }
    }

    // Функция для привязки обработчиков к кнопке загрузки
    function bindUploadButton(btn, formatIndex) {
      const newBtn = btn.cloneNode(true);
      btn.parentNode.replaceChild(newBtn, btn);
      
      newBtn.dataset.formatIndex = formatIndex;
      newBtn.addEventListener("click", function (e) {
        e.preventDefault();
        currentFormatIndex = parseInt(this.dataset.formatIndex);
        const modal = new bootstrap.Modal(document.getElementById("uploadModal"));
        modal.show();
        if (uploadedFiles[currentFormatIndex] && uploadedFiles[currentFormatIndex].length > 0) {
          displayUploadedFiles(currentFormatIndex);
        } else {
          document.getElementById("uploadedFilesList").innerHTML = '<p class="text-muted">Нет загруженных файлов</p>';
        }
      });
    }

    // Инициализация всех кнопок загрузки
    function initUploadButtons() {
      document.querySelectorAll(".upload-photos-btn").forEach((btn, idx) => {
        let formatIndex = btn.dataset.formatIndex;
        if (formatIndex === undefined) {
          formatIndex = idx;
          btn.dataset.formatIndex = formatIndex;
        }
        bindUploadButton(btn, parseInt(formatIndex));
      });
    }

    function displayUploadedFiles(formatIndex) {
      const list = document.getElementById("uploadedFilesList");
      if (!list) return;
      const files = uploadedFiles[formatIndex] || [];
      if (files.length === 0) {
        list.innerHTML = '<p class="text-muted">Нет загруженных файлов</p>';
        return;
      }
      let html = '<h6>Загруженные файлы:</h6><div class="uploaded-files-list">';
      files.forEach((file, i) => {
        html += `
          <div class="d-flex justify-content-between align-items-center mb-2 p-2 border rounded">
            <div>
              <i class="bi bi-file-image me-2"></i>
              <small>${escapeHtml(file.original_filename)}</small><br>
              <small class="text-muted">${(file.size / 1024).toFixed(1)} KB</small>
            </div>
            <button type="button" class="btn btn-sm btn-link text-danger delete-file-btn" 
                    data-filename="${file.saved_filename}" data-format-index="${formatIndex}" data-file-index="${i}">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        `;
      });
      html += "</div>";
      list.innerHTML = html;

      document.querySelectorAll(".delete-file-btn").forEach((btn) => {
        btn.addEventListener("click", function () {
          const filename = this.dataset.filename;
          const formatIdx = parseInt(this.dataset.formatIndex);
          const fileIdx = parseInt(this.dataset.fileIndex);
          deleteFile(filename, formatIdx, fileIdx);
        });
      });
    }
    
    // Функция для экранирования HTML
    function escapeHtml(str) {
      if (!str) return '';
      return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
      });
    }

    window.deleteFile = function (filename, formatIndex, fileIndex) {
      fetch("/delete_upload/" + encodeURIComponent(filename), {
        method: "POST",
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success && uploadedFiles[formatIndex]) {
            uploadedFiles[formatIndex].splice(fileIndex, 1);
            displayUploadedFiles(formatIndex);
            const photoCountSpan = document.getElementById(`photo-count-${formatIndex}`);
            if (photoCountSpan)
              photoCountSpan.textContent = `${uploadedFiles[formatIndex]?.length || 0} фото`;
            updateQuantityAndPrice(formatIndex);
          }
        })
        .catch((error) => console.error("Error:", error));
    };

    function handleFiles(files) {
      if (!files || files.length === 0) return;

      const allowedExtensions = ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "heic", "heif"];
      const validFiles = [];
      const currentCount = uploadedFiles[currentFormatIndex] ? uploadedFiles[currentFormatIndex].length : 0;

      if (currentCount + files.length > 100) {
        alert(`Максимум 100 фото на заказ. У вас уже ${currentCount} фото.`);
        return;
      }

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const extension = file.name.split(".").pop().toLowerCase();
        if (allowedExtensions.includes(extension)) {
          if (file.size <= 50 * 1024 * 1024) validFiles.push(file);
          else alert(`Файл ${file.name} слишком большой (максимум 50MB)`);
        } else {
          alert(`Неподдерживаемый формат: ${file.name}`);
        }
      }

      if (validFiles.length === 0) return;

      const formData = new FormData();
      formData.append("format", currentFormatIndex);
      validFiles.forEach((file) => formData.append("photos", file));

      const progressBar = document.getElementById("uploadProgress");
      const progressBarInner = progressBar.querySelector(".progress-bar");
      progressBar.style.display = "block";
      progressBarInner.style.width = "0%";
      progressBarInner.textContent = "0%";

      let simulatedProgress = 0;
      const progressInterval = setInterval(() => {
        if (simulatedProgress < 90) {
          simulatedProgress += 10;
          progressBarInner.style.width = simulatedProgress + "%";
          progressBarInner.textContent = simulatedProgress + "%";
        }
      }, 200);

      fetch("/upload_photos", { method: "POST", body: formData })
        .then((response) => response.json())
        .then((data) => {
          clearInterval(progressInterval);
          progressBarInner.style.width = "100%";
          progressBarInner.textContent = "100%";
          setTimeout(() => {
            progressBar.style.display = "none";
          }, 1000);

          if (data.success) {
            if (!uploadedFiles[currentFormatIndex])
              uploadedFiles[currentFormatIndex] = [];
            uploadedFiles[currentFormatIndex] = uploadedFiles[currentFormatIndex].concat(data.files);

            const photoCountSpan = document.getElementById(`photo-count-${currentFormatIndex}`);
            if (photoCountSpan)
              photoCountSpan.textContent = `${uploadedFiles[currentFormatIndex].length} фото`;

            displayUploadedFiles(currentFormatIndex);
            updateQuantityAndPrice(currentFormatIndex);
          }
          if (data.errors && data.errors.length)
            alert("Ошибки загрузки:\n" + data.errors.join("\n"));
        })
        .catch((error) => {
          clearInterval(progressInterval);
          console.error("Upload error:", error);
          alert("Ошибка загрузки файлов");
          progressBar.style.display = "none";
        });
    }

    // Обработчики загрузки
    const uploadArea = document.getElementById("uploadArea");
    const fileInput = document.getElementById("fileInput");
    const selectFilesBtn = document.getElementById("selectFilesBtn");

    if (uploadArea) {
      // Убираем клик на всю область, оставляем только на кнопку
      uploadArea.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadArea.style.backgroundColor = "rgba(255, 105, 180, 0.1)";
      });
      uploadArea.addEventListener("dragleave", () => {
        uploadArea.style.backgroundColor = "";
      });
      uploadArea.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadArea.style.backgroundColor = "";
        handleFiles(e.dataTransfer.files);
      });
    }
    if (selectFilesBtn) {
      selectFilesBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
      });
    }
    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        handleFiles(e.target.files);
        fileInput.value = "";
      });
    }

    const saveUploadedBtn = document.getElementById("saveUploadedBtn");
    if (saveUploadedBtn) {
      saveUploadedBtn.addEventListener("click", () => {
        bootstrap.Modal.getInstance(document.getElementById("uploadModal"))?.hide();
      });
    }

    // Добавление нового формата
    const orderItems = document.getElementById("order-items");
    const addBtn = document.getElementById("add-format-btn");

    function addNewFormat() {
      const firstItem = document.querySelector(".order-item");
      if (!firstItem) return;
      
      const newItem = firstItem.cloneNode(true);
      
      // Очищаем значения
      const formatSelect = newItem.querySelector(".format-select");
      // Выбираем первый доступный формат вместо пустого
      if (formatSelect.options.length > 0) {
        formatSelect.selectedIndex = 0;
      }
      
      newItem.querySelector(".quantity-input").value = "";
      newItem.querySelector(".item-subtotal").value = "0.00 BYN";
      
      // Удаляем старый ID и создаем новый
      const uploadBtn = newItem.querySelector(".upload-photos-btn");
      const newFormatIndex = itemCount;
      uploadBtn.dataset.formatIndex = newFormatIndex;
      
      // Обновляем photo-count
      const photoCountSpan = newItem.querySelector(".photo-count");
      photoCountSpan.id = `photo-count-${newFormatIndex}`;
      photoCountSpan.textContent = "0 фото";
      
      // Обновляем min-warning если есть
     // const minWarning = newItem.querySelector(".min-warning");
     // if (minWarning) {
     //   minWarning.id = `min-warning-${newFormatIndex}`;
    //    minWarning.style.display = "none";
    //  }
      
      // Добавляем кнопку удаления если её нет
      let removeBtn = newItem.querySelector(".remove-item");
      if (!removeBtn) {
        const btnContainer = newItem.querySelector(".mt-2");
        if (btnContainer) {
          removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.className = "btn btn-sm btn-link text-danger remove-item ms-2";
          removeBtn.innerHTML = '<i class="bi bi-trash"></i> Удалить формат';
          removeBtn.style.display = "inline-block";
          btnContainer.appendChild(removeBtn);
        }
      } else {
        removeBtn.style.display = "inline-block";
      }
      
      // Привязываем обработчик удаления
      if (removeBtn) {
        removeBtn = newItem.querySelector(".remove-item");
        removeBtn.addEventListener("click", function () {
          // Удаляем все загруженные файлы для этого формата
          if (uploadedFiles[newFormatIndex]) {
            // Опционально: удалить файлы с сервера
            delete uploadedFiles[newFormatIndex];
          }
          newItem.remove();
          calculateTotal();
        });
      }
      
      // Привязываем обработчик загрузки
      bindUploadButton(uploadBtn, newFormatIndex);
      
      // Добавляем элемент на страницу
      orderItems.appendChild(newItem);
      itemCount++;
    }

    if (addBtn) {
      // Удаляем старый обработчик и добавляем новый
      const newAddBtn = addBtn.cloneNode(true);
      addBtn.parentNode.replaceChild(newAddBtn, addBtn);
      newAddBtn.addEventListener("click", function (e) {
        e.preventDefault();
        addNewFormat();
      });
    }

    // Обработка изменения формата
    document.addEventListener("change", function (e) {
      if (e.target.classList.contains("format-select")) {
        const item = e.target.closest(".order-item");
        const btn = item.querySelector(".upload-photos-btn");
        if (btn && btn.dataset.formatIndex) {
          const idx = parseInt(btn.dataset.formatIndex);
          updateQuantityAndPrice(idx);
        }
      }
    });

    // Инициализируем существующие кнопки
    initUploadButtons();

    // Проверка перед отправкой
    const orderForm = document.getElementById("orderForm");
if (orderForm) {
  orderForm.addEventListener("submit", function (e) {
    let hasError = false;
    let hasAnyPhotos = false;
    
    document.querySelectorAll(".order-item").forEach((item, idx) => {
      const formatSelect = item.querySelector(".format-select");
      if (formatSelect && formatSelect.value) {
        const btn = item.querySelector(".upload-photos-btn");
        const formatIndex = btn ? parseInt(btn.dataset.formatIndex) : idx;
        const photoCount = uploadedFiles[formatIndex] ? uploadedFiles[formatIndex].length : 0;
        
        if (photoCount > 0) {
          hasAnyPhotos = true;
        }
        
        // Только предупреждение, но не блокировка
        if (photoCount === 0) {
          console.warn(`Для формата "${formatSelect.options[formatSelect.selectedIndex]?.text}" не загружены фотографии`);
        }
      }
    });
    
    if (!hasAnyPhotos) {
      alert("Загрузите хотя бы одну фотографию!");
      hasError = true;
      e.preventDefault();
    }
    
    if (hasError) e.preventDefault();
  });
}
  });