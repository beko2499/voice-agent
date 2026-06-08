-- 1. إنشاء جدول المواعيد
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status TEXT DEFAULT 'CONFIRMED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. منع الحجز المزدوج في نفس اليوم والوقت
ALTER TABLE appointments ADD CONSTRAINT unique_appointment_datetime UNIQUE (appointment_date, appointment_time);

-- 3. تفعيل الـ RLS (Row Level Security)
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

-- 4. السماح بقراءة وكتابة البيانات فقط لمفتاح السيرفر (Service Role) أو الدوال الداخلية
CREATE POLICY "Allow Service Role full access" 
ON appointments 
FOR ALL 
TO service_role 
USING (true) 
WITH CHECK (true);

-- ملاحظة: أوقات العمل الافتراضية في هذا المثال هي من 9:00 صباحاً حتى 5:00 مساءً.
-- سنقوم ببرمجة دالة البحث لتبحث عن الأوقات الغير محجوزة في هذا الجدول.
