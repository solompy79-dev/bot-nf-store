import * as React from 'react'

import {
  Body,
  Container,
  Head,
  Heading,
  Html,
  Img,
  Preview,
  Section,
  Text,
} from '@react-email/components'

interface SignupEmailProps {
  siteName: string
  siteUrl: string
  recipient: string
  confirmationUrl: string
  token?: string
}

export const SignupEmail = ({
  siteName,
  token,
}: SignupEmailProps) => (
  <Html lang="ar" dir="rtl">
    <Head />
    <Preview>كود تأكيد حسابك في {siteName}</Preview>
    <Body style={main}>
      <Container style={container}>
        <Section style={{ textAlign: 'center' as const, margin: '0 0 24px' }}>
          <Img
            src="https://ishtraki.store/__l5e/assets-v1/98da2c32-64f6-4339-8d45-24be5a3fd87c/ishtiraki-plus-logo.png"
            alt="اشتراكي بلس"
            width="140"
            style={{ margin: '0 auto', display: 'block' }}
          />
        </Section>
        <Heading style={h1}>كود تأكيد حسابك</Heading>
        <Text style={text}>
          أهلاً بيك في {siteName}! دي رسالة تأكيد إنشاء حسابك. استخدم الكود ده لتفعيل الحساب:
        </Text>
        <Section style={codeBox}>
          <Text style={codeText}>{token ?? '------'}</Text>
        </Section>
        <Text style={text}>
          الكود صالح لمدة ساعة. اكتبه في صفحة التسجيل عندنا وحسابك هيتفعل فوراً.
        </Text>
        <Text style={footer}>
          لو مطلبتش الكود ده، تجاهل الرسالة ببساطة.
        </Text>
      </Container>
    </Body>
  </Html>
)

export default SignupEmail

const main = { backgroundColor: '#ffffff', fontFamily: 'Tahoma, Arial, sans-serif' }
const container = { padding: '32px 28px', maxWidth: '520px', margin: '0 auto' }
const brand = { fontSize: '24px', fontWeight: 900 as const, color: '#0d0d1f', textAlign: 'center' as const, margin: '0 0 24px' }
const h1 = { fontSize: '22px', fontWeight: 'bold' as const, color: '#0d0d1f', margin: '0 0 16px', textAlign: 'center' as const }
const text = { fontSize: '15px', color: '#333', lineHeight: '1.7', margin: '0 0 20px', textAlign: 'right' as const }
const codeBox = {
  background: 'linear-gradient(135deg, #8b5cf6 0%, #c4b5fd 100%)',
  borderRadius: '16px',
  padding: '24px',
  textAlign: 'center' as const,
  margin: '24px 0',
}
const codeText = {
  fontSize: '38px',
  fontWeight: 900 as const,
  color: '#ffffff',
  letterSpacing: '10px',
  margin: 0,
  fontFamily: 'monospace',
}
const footer = { fontSize: '12px', color: '#999999', margin: '30px 0 0', textAlign: 'center' as const }
