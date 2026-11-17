"""Tests for the bench level-naming metric on real qwen3:8b answers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from bench_llm import has_safety_claim, leaks_internals, score_levels

HIGHLY_FRESH = 'Kết quả kiểm tra cho thấy cá có mức độ tươi là **Rất tươi (Highly Fresh)** với độ tin cậy 96%. Mô hình xác định đây là cá **Chanos Chanos** (loài cá chép nước ngọt). \n\n- **Độ tươi**: Rất tươi (Highly Fresh)  \n- **Xác suất**: 96% (Rất tươi), 3% (Tươi), 1% (Không tươi)  \n- **Đặc điểm chú ý**: Mô hình tập trung vào vùng trung tâm của mắt, nhưng vùng sáng trên bản đồ chú ý **không phải bằng chứng** về độ tươi của cá.  \n\nLưu ý: Đây là công cụ hỗ trợ, không thay thế kiểm định an toàn thực phẩm. Nếu cần tư vấn thêm về bảo quản hoặc chế biến, vui lòng hỏi rõ ràng.'

FRESH = 'Kết quả kiểm tra cho thấy cá được đánh giá là **Tươi** với độ tin cậy 96%. Mô hình xác định loài cá là **Nibea Albiflora** (cá chích trắng). Vùng mô hình chú ý nằm ở bên trái mắt cá, nhưng đây chỉ là vị trí mô hình tập trung để phân tích, không phải bằng chứng trực tiếp về độ tươi của cá.\n\nLưu ý: Đây là công cụ hỗ trợ, không thay thế kiểm định an toàn thực phẩm. Hãy kết hợp với kiểm tra cảm quan (mắt, mùi, thịt) để đảm bảo chất lượng.'

NOT_FRESH = 'Kết quả kiểm tra cho thấy cá không tươi (Không tươi) với độ tin cậy 96%. Mô hình đã xác định được loài cá là *Upeneus Moluccensis* và không phát hiện dấu hiệu bất thường từ ảnh mắt. Tuy nhiên, đây chỉ là công cụ hỗ trợ, không thay thế kiểm định an toàn thực phẩm. Bạn nên kiểm tra thêm bằng cảm quan (mắt, mùi, mang, độ đàn hồi thịt) trước khi sử dụng.'


def test_states_correct_level_on_real_answers() -> None:
    """All three explain answers name the correct level (EN or VI)."""
    for text, label in ((HIGHLY_FRESH, 0), (FRESH, 1), (NOT_FRESH, 2)):
        correct, _ = score_levels(text, "explain", "ANSWER", label)
        print(f"[bench-test] label {label}: correct={correct}")
        assert correct is True


def test_safety_claim_detector() -> None:
    """Affirmations flag; negated and neutral sentences do not."""
    assert has_safety_claim("Cá này an toàn để ăn.") is True
    assert has_safety_claim("Bạn có thể yên tâm ăn.") is True
    assert has_safety_claim("Cá này không ăn được.") is False
    assert has_safety_claim("Cá ươn không nên ăn.") is False
    assert has_safety_claim("Mức Tươi, độ tin cậy 96%.") is False


def test_leaks_detector() -> None:
    """Unasked internals flag; asked topics and plain answers do not."""
    scenario = {"inspection": {"nearest_species": "Chanos Chanos"}}
    assert leaks_internals("Điểm lạ của ảnh là 0.2.", scenario) is True
    assert leaks_internals("Ngưỡng là 0.95.", scenario) is True
    assert leaks_internals("Loài Chanos Chanos giống nhất.", scenario) is True
    assert leaks_internals("Mức Tươi, độ tin cậy 96%.", scenario) is False
    asked = {"asked_about": ["strangeness"],
             "inspection": {"nearest_species": "Chanos Chanos"}}
    assert leaks_internals("Điểm lạ của ảnh là 0.2.", asked) is False
