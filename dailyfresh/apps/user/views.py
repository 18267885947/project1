from django.shortcuts import render,redirect
from django.urls import reverse
from django.http import HttpResponse
from django.core.mail import send_mail
from django.contrib.auth import authenticate,login,logout
import re
from celery_tasks.tasks import send_register_active_email
from apps.user.models import User,Address,AddressManager
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo,OrderGoods
from django.views.generic import View
from django.core.paginator import Paginator
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from utils.maxin import LoginRequiredMixin
from django_redis import get_redis_connection


# Create your views here.
def register(request):
    if request.method=='GET':
        return render(request, 'register.html')
    else:
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据处理
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 返回应答
        return redirect(reverse('goods:index'))


def register_handle(request):
    '''进行注册处理'''
    #接受数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow=request.POST.get('allow')

    #进行数据处理
    if not all([username,password,email]):
        return render(request, 'register.html', {'errmsg': '数据不完整'})

    #校验邮箱
    if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

    if allow !='on':
        return render(request, 'register.html', {'errmsg': '请同意协议'})
    #校验用户名是否重复
    try:
        user=User.objects.get(username=username)
    except User.DoesNotExist:
        user=None
    if user:
        return render(request, 'register.html', {'errmsg': '用户已存在'})

    #进行业务处理：进行用户注册
    user=User.objects.create_user(username, email, password)
    user.is_active=0
    user.save()

    #返回应答
    return redirect(reverse('goods:index'))


class RegisterView(View):
    #注册
    def get(self,request):
        return render(request, 'register.html')

    def post(self,request):
        #接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据处理
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        #校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        #发送激活链接
        #加密用户的身份信息
        serializer=Serializer(settings.SECRET_KEY,3600)
        info={'confirm':user.id}
        #拿到的info是一个bytes信息，需要进行解码。
        token=serializer.dumps(info)
        token=token.decode()
        #发邮件
        # subject='天天生鲜欢迎信息'
        # message=''
        # sender=settings.EMAIL_FROM
        # receiver=[email]
        # html_message='<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>'%(username,token,token)
        # send_mail(subject, message, sender, receiver, html_message=html_message)
        send_register_active_email.delay(email,username,token)

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    #用户激活
    def get(self,request,token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info=serializer.loads(token)
            #获取待激活的用户id
            user_id=info['confirm']
            #根据id获取用户信息
            user=User.objects.get(id=user_id)
            user.is_active=1
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')


class LoginView(View):
    def get(self,request):
        #显示登陆页面
        if 'username' in request.COOKIES:
            username=request.COOKIES.get('username')
            checked='checked'
        else:
            username=''
            checked=''
        return render(request,'login.html',{'username':username,'checked':checked})
    def post(self,request):
        #接受数据
        username=request.POST.get('username')
        password=request.POST.get('pwd')
        if not all([username,password]):
            return render(request,'login.html',{'errmsg':'数据不完整'})
        user=authenticate(username=username,password=password)
        if user is not None:
            if user.is_active:#用户已激活
                login(request,user)#记录登陆状态
                next_url=request.GET.get('next',reverse('goods:index'))#默认跳转到首页
                response=redirect(next_url)#跳转到next_url
                remember=request.POST.get('remember')
                if remember== 'on':#记住用户名
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                return render(request,'login.html',{'errmsg':'账户未激活'})
        else:
            return render(request,'login.html',{'errmsg':'用户名或密码错误'})


class LogoutView(View):
    def get(self,request):
        logout(request)
        return redirect(reverse('goods:index'))

#/user
class UserInfoView(LoginRequiredMixin,View):
    def get(self,request):
        user=request.user#如果用户未登录anonymousUser类的实例 如果用户登录，user类的实例
        address=Address.objects.get_default_address(user)
        # from redis import StrictRedis
        # sr=StrictRedis(host='127.0.0.1',port='6379',db=9)
        con=get_redis_connection('default')
        history_key='history_%d'%user.id
        #获取用户最新浏览的5个商品的id
        sku_ids=con.lrange(history_key,0,4)
        #从数据库中查询用户浏览的商品的具体信息
        # goods_li=GoodsSKU.objects.filter(id__in=sku_ids)
        # goods_res=[]
        # for a_id in sku_ids:
        #     for goods in goods_li:
        #         if a_id==goods_li:
        #             goods_res.append(goods)
        #遍历获取用户浏览的商品信息
        goods_li=[]
        for id in sku_ids:
            goods=GoodsSKU.objects.get(id = id)
            goods_li.append(goods)
        context={
            'page': 'user',
            'address': address,
            'goods_li':goods_li
        }
        return render(request,'user_center_info.html',context)

#/user/order
class UserOrderView(LoginRequiredMixin,View):
    def get(self,request,page):
        user=request.user
        orders=OrderInfo.objects.filter(user=user).order_by('-create_time')
        #遍历获取订单商品信息
        for order in orders:
            #根据order_id查询订单商品信息
            order_skus=OrderGoods.objects.filter(order_id=order.order_id)
            for order_sku in order_skus:
                #计算小计
                amount=order_sku.count*order_sku.price
                #动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount=amount
            order.status_name=OrderInfo.ORDER_STATUS[order.order_status]
            #动态给order增加属性，保存订单商品的信息
            order.order_skus=order_skus
        #分页
        paginator=Paginator(orders,1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = 1
        # 获取第page页的Page实例对象
        order_page= paginator.page(page)
        # 进行页码的控制，页面上最多显示5个页码
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)
        context={
            "order_page":order_page,
            "pages":pages,
            'page':'order'
        }

        return render(request,'user_center_order.html',context)


#/user/address
class AddressView(LoginRequiredMixin,View):
    def get(self,request):
        user=request.user
        #获取用户默认地址
        '''
        try:
            address=Address.objects.get(user=user,is_default=True)
        except Address.DoesNotExist:
            address=None
        '''
        address = Address.objects.get_default_address(user)
        return render(request,'user_center_site.html',{'page':'address','address':address})

    def post(self,req):
        '''地址的添加'''
        #接收数据
        receiver=req.POST.get('receiver')
        addr=req.POST.get('addr')
        zip_code=req.POST.get('zip_code')
        phone=req.POST.get('phone')
        #校验数据
        if not all([receiver,addr,phone]):
            return render(req,'user_center_site.html',{'errmsg':'数据不完整'})
        #校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
            return render(req,'user_center_site.html',{'errmsg':'数据格式不正确'})

        user=req.user
        '''
        try:
            address=Address.objects.get(user=user,is_default=True)
        except Address.DoesNotExist:
            address=None
        '''
        address=Address.objects.get_default_address(user)

        if address:
            is_default=False
        else:
            is_default=True
        Address.objects.create(user=user,receiver=receiver,addr=addr,zip_code=zip_code,phone=phone,is_default=is_default)
        return redirect(reverse('user:address'))